"""Custom QA Pattern with fallback mechanism.

Features:
- Uses LLM for question answering
- Falls back to memory search when LLM fails
- Graceful error handling
- Tool retry with fallback
"""

from __future__ import annotations

import json
from typing import Any

from openagents.interfaces.capabilities import PATTERN_EXECUTE, PATTERN_REACT
from openagents.interfaces.pattern import PatternPlugin


class QAPatternWithFallback(PatternPlugin):
    """Question Answering Pattern with fallback mechanism.

    Fallback chain:
    1. Try LLM with full context
    2. If LLM fails -> try with simplified prompt
    3. If still fails -> use memory search results as answer
    4. If no memory -> return error message
    """

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config=config or {}, capabilities={PATTERN_EXECUTE, PATTERN_REACT})
        self._max_steps = self.config.get("max_steps", 3)
        self._fallback_enabled = self.config.get("fallback_enabled", True)

    # ============== Default implementations ==============

    async def emit(self, event_name: str, **payload: Any) -> None:
        """Emit event using context's event_bus."""
        ctx = self.context
        if ctx.event_bus:
            await ctx.event_bus.emit(
                event_name,
                agent_id=ctx.agent_id,
                session_id=ctx.session_id,
                **payload,
            )

    async def call_tool(
        self,
        tool_id: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Call tool with fallback support."""
        ctx = self.context
        if tool_id not in ctx.tools:
            raise KeyError(f"Tool '{tool_id}' is not registered")

        tool = ctx.tools[tool_id]
        await self.emit("tool.called", tool_id=tool_id, params=params or {})

        try:
            result = await tool.invoke(params or {}, ctx)
            ctx.tool_results.append({"tool_id": tool_id, "result": result})
            await self.emit("tool.succeeded", tool_id=tool_id)
            return result
        except Exception as exc:
            await self.emit("tool.failed", tool_id=tool_id, error=str(exc))

            # Try fallback
            if hasattr(tool, "fallback"):
                try:
                    fallback_result = await tool.fallback(exc, params or {}, ctx)
                    if fallback_result is not None:
                        await self.emit("tool.fallback_used", tool_id=tool_id)
                        return fallback_result
                except Exception:
                    pass

            # Re-raise original exception
            raise

    async def call_llm(
        self,
        *,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Call LLM with error handling."""
        ctx = self.context
        if ctx.llm_client is None:
            raise RuntimeError("No LLM client configured")

        await self.emit("llm.called", model=model)
        try:
            result = await ctx.llm_client.complete(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            await self.emit("llm.succeeded", model=model)
            return result
        except Exception as exc:
            await self.emit("llm.failed", error=str(exc))
            raise

    # ============== Pattern execution ==============

    async def execute(self) -> Any:
        """Execute the QA pattern with fallback."""
        ctx = self.context

        try:
            # Step 1: Build prompt with context
            messages = self._build_prompt()

            # Step 2: Call LLM
            response = await self.call_llm(messages=messages)

            # Step 3: Parse response
            result = self._parse_response(response)
            return result

        except Exception as exc:
            # Fallback: Use memory search results
            if self._fallback_enabled:
                return await self._fallback_to_memory(str(exc))
            raise

    async def _fallback_to_memory(self, error: str) -> str:
        """Fallback to memory search when LLM fails."""
        ctx = self.context

        # Get search results from memory
        history = ctx.memory_view.get("history", [])
        search_query = ctx.memory_view.get("search_query", ctx.input_text)
        memory_source = ctx.memory_view.get("memory_source", "none")

        if history:
            # Build answer from memory
            context_parts = [f"Previous conversation (source: {memory_source}):"]
            for i, item in enumerate(history, 1):
                context_parts.append(f"{i}. Q: {item.get('input', '')}")
                if item.get("output"):
                    context_parts.append(f"   A: {item.get('output', '')[:200]}")

            fallback_prompt = f"""Based on previous conversation context, answer the question.

Previous Context:
{chr(10).join(context_parts)}

Current Question: {ctx.input_text}

Provide a helpful answer based on the previous context. If the context doesn't contain relevant information, say so honestly.

Answer:"""

            try:
                # Try LLM again with simpler prompt
                messages = [{"role": "user", "content": fallback_prompt}]
                response = await self.call_llm(messages=messages, temperature=0.7)
                await self.emit("qa.fallback_success", source=memory_source)
                return f"[From Memory] {response}"
            except Exception:
                # Last resort: return raw memory
                await self.emit("qa.fallback_raw_memory", source=memory_source)
                raw_info = "\n".join(
                    f"- {item.get('input', '')}: {str(item.get('output', ''))[:100]}"
                    for item in history[:3]
                )
                return f"[Memory Only] Related past conversations:\n{raw_info}\n\nQuestion: {ctx.input_text}"

        # No memory available
        await self.emit("qa.no_context", error=error)
        return f"I couldn't process your question due to an error: {error}. And I don't have any previous conversation history to fall back on."

    def _build_prompt(self) -> list[dict[str, str]]:
        """Build prompt with context."""
        ctx = self.context
        history = ctx.memory_view.get("history", [])
        memory_source = ctx.memory_view.get("memory_source", "none")

        # Build system prompt
        system_prompt = """You are a helpful AI assistant that answers questions based on the provided context.

Instructions:
- Use the conversation history to provide personalized answers
- If the history is relevant, cite it in your answer
- If you don't know the answer, say so honestly
- Be concise but informative"""

        # Build user prompt with context
        context_parts = []
        if history:
            context_parts.append("Conversation History:")
            for item in history:
                q = item.get("input", "")
                a = item.get("output", "")
                if q:
                    context_parts.append(f"User: {q}")
                if a:
                    context_parts.append(f"Assistant: {a[:300]}")

        user_prompt = ctx.input_text
        if context_parts:
            user_prompt = f"{chr(10).join(context_parts)}\n\nCurrent Question: {ctx.input_text}"

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def _parse_response(self, response: str) -> str:
        """Parse LLM response."""
        # Try to parse as JSON
        try:
            data = json.loads(response)
            if isinstance(data, dict):
                if data.get("type") == "final":
                    return data.get("content", response)
                return data.get("content", response)
        except json.JSONDecodeError:
            pass

        # Return as-is
        return response
