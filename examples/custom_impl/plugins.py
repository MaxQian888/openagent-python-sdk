from __future__ import annotations

from typing import Any

from openagents.interfaces.capabilities import (
    PATTERN_EXECUTE,
    PATTERN_REACT,
    SKILL_CONTEXT_AUGMENT,
    SKILL_METADATA,
    SKILL_POST_RUN,
    SKILL_PRE_RUN,
    SKILL_SYSTEM_PROMPT,
    SKILL_TOOL_FILTER,
    SKILL_TOOLS,
    TOOL_INVOKE,
    supports,
)
from openagents.interfaces.pattern import ExecutionContext
from openagents.interfaces.tool import ToolPlugin


# ---------------------------------------------------------------------------
# DemoSkill — demonstrates all 6 skill capability hooks.
#
# Capability mapping:
#   SKILL_SYSTEM_PROMPT  → get_system_prompt()
#   SKILL_TOOLS          → get_tools()
#   SKILL_METADATA       → get_metadata()
#   SKILL_CONTEXT_AUGMENT → augment_context()
#   SKILL_TOOL_FILTER    → filter_tools()
#   SKILL_PRE_RUN        → before_run()
#   SKILL_POST_RUN       → after_run()
#
# Observable effects (stored in context.state for verification):
#   _skill_augmented   — set by augment_context
#   _pre_run_ran       — set by before_run
#   _post_run_ran      — set by after_run
#   _skill_name         — set by get_metadata via augment_context
#   _filtered_tools     — set by filter_tools
#   _last_result        — set by after_run
# ---------------------------------------------------------------------------

_SKILLS_KEEP = {"echo_tool", "calc_tool", "echo", "calc", "builtin_search", "search", "skill_search"}


class DemoSkill:
    """Skill with all 6 hooks active. Each hook writes to context.state."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.capabilities = {
            SKILL_SYSTEM_PROMPT,
            SKILL_TOOLS,
            SKILL_METADATA,
            SKILL_CONTEXT_AUGMENT,
            SKILL_TOOL_FILTER,
            SKILL_PRE_RUN,
            SKILL_POST_RUN,
        }

    # -- SKILL_SYSTEM_PROMPT -----------------------------------------------

    def get_system_prompt(self, context: Any | None = None) -> str:
        self._log_hook("get_system_prompt", context)
        return (
            "You are DemoSkill — a skill that demonstrates the full "
            "capability hook surface. "
            "You have access to echo, calc, and search tools."
        )

    # -- SKILL_TOOLS -------------------------------------------------------

    def get_tools(self) -> list[Any]:
        # Return tool refs dicts (same format as agent.json tools[]).
        # These are merged into the agent's tool set at load time.
        return [{"type": "builtin_search", "id": "skill_search", "enabled": True}]

    def _log_hook(self, name: str, context: Any | None) -> None:
        """Append hook call to context.state._hook_log if context is available."""
        if context is not None and hasattr(context, "state"):
            state = context.state
            state.setdefault("_hook_log", []).append(name)
            state.setdefault("_skills_active", set()).add(self.__class__.__name__)

    # -- SKILL_METADATA -----------------------------------------------------

    def get_metadata(self) -> dict[str, Any]:
        return {"skill_version": "1.0", "skill_name": "demo_skill"}

    # -- SKILL_CONTEXT_AUGMENT ----------------------------------------------

    def augment_context(self, context: Any) -> None:
        self._log_hook("augment_context", context)
        context.state["_skill_augmented"] = True
        meta = self.get_metadata()
        context.state["_skill_name"] = meta["skill_name"]
        context.state["_skill_version"] = meta["skill_version"]

    # -- SKILL_TOOL_FILTER --------------------------------------------------

    def filter_tools(
        self, tools: dict[str, Any], context: Any | None = None
    ) -> dict[str, Any]:
        self._log_hook("filter_tools", context)
        # Keep only safe tools; remove everything else (e.g. execute_command).
        allowed = {k: v for k, v in tools.items() if k in _SKILLS_KEEP}
        context.state["_filtered_tools"] = list(allowed.keys()) if context else list(allowed.keys())
        return allowed

    # -- SKILL_PRE_RUN ------------------------------------------------------

    async def before_run(self, context: Any) -> None:
        self._log_hook("before_run", context)
        context.state["_pre_run_ran"] = True

    # -- SKILL_POST_RUN -----------------------------------------------------

    async def after_run(self, context: Any, result: Any) -> Any:
        self._log_hook("after_run", context)
        context.state["_post_run_ran"] = True
        context.state["_last_result"] = str(result)
        return result  # pass through

    # -- internal -----------------------------------------------------------

    def _log_hook(self, name: str, context: Any | None) -> None:
        """Append hook name to scratch list for run_demo verification."""
        if context is not None and hasattr(context, "state"):
            key = "_hook_log"
            log: list = list(context.state.get(key, []))
            log.append(name)
            context.state[key] = log


# ---------------------------------------------------------------------------
# EchoTool — a tool that proves skill augmentation ran.
# It reads _skill_augmented from context.state to produce contextual output.
# ---------------------------------------------------------------------------

class EchoTool(ToolPlugin):
    name = "echo_tool"
    description = "Echoes text with skill context metadata."

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config=config or {}, capabilities={TOOL_INVOKE})
        self._prefix = self.config.get("prefix", "echo")

    async def invoke(self, params: dict[str, Any], context: Any) -> Any:
        text = str(params.get("text", "")).strip()
        skill_name = context.state.get("_skill_name", "unknown")
        skill_ver = context.state.get("_skill_version", "?")
        return {
            "text": text,
            "prefix": self._prefix,
            "skill": f"{skill_name}@{skill_ver}",
        }

    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to echo"},
            },
            "required": ["text"],
        }


# ---------------------------------------------------------------------------
# CalcTool — simple calculator tool to verify filter_tools worked.
# ---------------------------------------------------------------------------

class CalcTool(ToolPlugin):
    name = "calc_tool"
    description = "Performs basic arithmetic."

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config=config or {}, capabilities={TOOL_INVOKE})

    async def invoke(self, params: dict[str, Any], context: Any) -> Any:
        expr = str(params.get("expression", "")).strip()
        try:
            # safe eval — only digits and basic operators
            result = eval(expr, {"__builtins__": {}}, {})  # noqa: S307
            return {"expression": expr, "result": result}
        except Exception as exc:  # noqa: BLE001
            return {"expression": expr, "error": str(exc)}

    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "e.g. 2 + 3 * 4"},
            },
            "required": ["expression"],
        }


# ---------------------------------------------------------------------------
# DemoPattern — minimal ReAct-style pattern that works with MockLLM.
#
# MockLLM.complete() parses the prompt and returns:
#   • {"type":"tool_call","tool":"<id>","params":{"query":"..."}}
#     when input starts with "/tool <id> ..."
#   • {"type":"final","content":"Echo: <text> (history=<n>)"}
#     for regular text
#
# So run_demo uses "/tool echo_tool hello" to trigger a tool call,
# and the pattern forwards it to the tool and returns the result.
# ---------------------------------------------------------------------------

class DemoPattern:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.capabilities = {PATTERN_EXECUTE, PATTERN_REACT}
        self.context: ExecutionContext | None = None

    async def setup(
        self,
        agent_id: str,
        session_id: str,
        input_text: str,
        state: dict[str, Any],
        tools: dict[str, Any],
        llm_client: Any,
        llm_options: Any,
        event_bus: Any,
        transcript: list | None = None,
        session_artifacts: list | None = None,
        assembly_metadata: dict | None = None,
        **kwargs: Any,
    ) -> None:
        self.context = ExecutionContext(
            agent_id=agent_id,
            session_id=session_id,
            input_text=input_text,
            state=state,
            tools=tools,
            llm_client=llm_client,
            llm_options=llm_options,
            event_bus=event_bus,
        )
        if transcript is not None:
            self.context.transcript = list(transcript)
        if session_artifacts is not None:
            self.context.session_artifacts = list(session_artifacts)
        if assembly_metadata is not None:
            self.context.assembly_metadata = dict(assembly_metadata)

    async def react(self) -> dict[str, Any]:
        """One step: ask the LLM (Anthropic) what to do.

        With a real LLM the response is free-form text. We try to parse JSON,
        and fall back to wrapping the text as a final response.
        The LLM's system prompt guides JSON output, but we handle any format.
        """
        assert self.context is not None
        ctx = self.context

        # Build prompt — skill's system_prompt gets injected by runtime via
        # context.system_prompt_fragments, but we also include a direct
        # instruction for JSON output.
        history_text = self._format_history(ctx.memory_view.get("history", []))
        tools_text = self._format_tools_description()
        system_prompt = (
            ctx.state.get("_skill_system_prompt", "") +
            "\n\nReturn your response as JSON only, no markdown. "
            "Use this format:\n"
            '{"type":"final","content":"your answer"}\n'
            '{"type":"tool_call","tool":"<tool_id>","params":{"query":"..."}}\n'
            "Never include any text outside the JSON."
        )

        prompt = (
            f"{ctx.input_text}\n\n"
            f"CONVERSATION_HISTORY:\n{history_text}\n"
            f"AVAILABLE_TOOLS:\n{tools_text}\n"
            "Respond with JSON only."
        )
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]
        raw = await ctx.llm_client.complete(messages=messages)
        return self._parse_action(raw)

    def _parse_action(self, raw: str) -> dict[str, Any]:
        """Parse LLM response into an action dict.

        Tries JSON first, then searches for JSON in the text,
        falls back to wrapping as a final response.
        """
        import json
        # Try direct JSON
        try:
            return json.loads(raw.strip())
        except json.JSONDecodeError:
            pass
        # Try finding JSON block in text
        start, end = raw.find("{"), raw.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                pass
        return {"type": "final", "content": raw.strip()}

    def _format_history(self, history: list) -> str:
        if not history:
            return "(no history)"
        lines = []
        for item in history:
            if isinstance(item, dict):
                u = item.get("input", "")
                a = item.get("output", "")
                if u:
                    lines.append(f"User: {u}")
                if a:
                    lines.append(f"Assistant: {a}")
        return "\n".join(lines) if lines else "(no history)"

    def _format_tools_description(self) -> str:
        ctx = self.context
        lines = []
        for tid in sorted(ctx.tools.keys()):
            tool = ctx.tools[tid]
            desc = getattr(tool, "description", "") or ""
            schema = getattr(tool, "schema", lambda: {})()
            props = schema.get("properties", {}) if isinstance(schema, dict) else {}
            params = ", ".join(f"{k}: {v.get('type','any')}" for k, v in props.items())
            lines.append(f"  - {tid}: {desc} ({params})" if params else f"  - {tid}: {desc}")
        return "\n".join(lines) if lines else "  (no tools)"

    async def execute(self) -> Any:
        """Execute the step returned by react()."""
        assert self.context is not None
        ctx = self.context
        action = await self.react()
        action_type = action.get("type", "final")

        if action_type == "tool_call":
            tool_id = action.get("tool") or action.get("tool_id")
            params = action.get("params") or {}
            tool = ctx.tools.get(tool_id)
            if tool is None:
                ctx.state["_runtime_last_output"] = f"[ERROR] Unknown tool: {tool_id}"
                return ctx.state["_runtime_last_output"]
            result = await tool.invoke(params, ctx)
            output = f"[{tool_id}] => {result}"
            ctx.state["_runtime_last_output"] = output
            return output

        content = action.get("content", "")
        ctx.state["_runtime_last_output"] = content
        return content
