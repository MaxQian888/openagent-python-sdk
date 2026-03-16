"""Builtin skill implementations."""

from __future__ import annotations

from typing import Any

from openagents.interfaces.capabilities import (
    SKILL_EXECUTE,
    SKILL_GET_PROMPT,
    SKILL_GET_TOOLS,
)
from openagents.interfaces.skill import SkillPlugin


class ResearcherSkill(SkillPlugin):
    """Research skill - specialized in information gathering and analysis.

    Tools typically used: search, http_request, url_parse
    """

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(
            config=config or {},
            capabilities={SKILL_EXECUTE, SKILL_GET_PROMPT, SKILL_GET_TOOLS},
        )
        self._focus = self.config.get("focus", "general")  # general, academic, news

    async def execute(self, context: Any) -> Any:
        """Execute research task."""
        # This delegates to the agent's pattern
        # The skill primarily provides the system prompt
        return {"status": "ready", "skill": "researcher"}

    def get_system_prompt(self, context: Any | None = None) -> str:
        focus = self._focus
        return (
            "You are a research specialist. Your role is to gather, analyze, "
            "and synthesize information on any topic.\n\n"
            f"Research focus: {focus}\n\n"
            "Guidelines:\n"
            "- Use multiple sources to verify information\n"
            "- Distinguish between facts and opinions\n"
            "- Provide citations when possible\n"
            "- Be objective and balanced\n"
            "- Follow up on interesting leads\n"
        )

    def get_tools(self) -> list[str]:
        return ["builtin_search", "http_request", "url_parse", "grep_files"]


class CoderSkill(SkillPlugin):
    """Coding skill - specialized in programming and technical tasks.

    Tools typically used: read_file, write_file, execute_command, grep_files
    """

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(
            config=config or {},
            capabilities={SKILL_EXECUTE, SKILL_GET_PROMPT, SKILL_GET_TOOLS},
        )
        self._languages = self.config.get("languages", ["python", "javascript"])
        self._strict = self.config.get("strict", True)

    async def execute(self, context: Any) -> Any:
        """Execute coding task."""
        return {"status": "ready", "skill": "coder"}

    def get_system_prompt(self, context: Any | None = None) -> str:
        languages = ", ".join(self._languages)
        strict = "Enable" if self._strict else "Disable"
        return (
            f"You are a coding specialist. Your role is to write, debug, "
            f"and refactor code.\n\n"
            f"Languages: {languages}\n"
            f"Type checking: {strict}\n\n"
            "Guidelines:\n"
            "- Write clean, readable code with proper naming\n"
            "- Add docstrings and comments for complex logic\n"
            "- Handle errors gracefully\n"
            "- Consider edge cases\n"
            "- Write tests when appropriate\n"
            "- Follow language-specific best practices\n"
        )

    def get_tools(self) -> list[str]:
        return [
            "read_file",
            "write_file",
            "list_files",
            "delete_file",
            "execute_command",
            "grep_files",
            "ripgrep",
        ]


class WriterSkill(SkillPlugin):
    """Writing skill - specialized in content creation and editing.

    Tools typically used: text_transform, json_parse
    """

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(
            config=config or {},
            capabilities={SKILL_EXECUTE, SKILL_GET_PROMPT, SKILL_GET_TOOLS},
        )
        self._style = self.config.get("style", "informative")
        self._tone = self.config.get("tone", "professional")

    async def execute(self, context: Any) -> Any:
        """Execute writing task."""
        return {"status": "ready", "skill": "writer"}

    def get_system_prompt(self, context: Any | None = None) -> str:
        return (
            "You are a writing specialist. Your role is to create clear, "
            "engaging, and well-structured content.\n\n"
            f"Writing style: {self._style}\n"
            f"Tone: {self._tone}\n\n"
            "Guidelines:\n"
            "- Know your audience\n"
            "- Structure content logically\n"
            "- Use clear, concise language\n"
            "- Vary sentence structure\n"
            "- Edit and proofread\n"
            "- Format appropriately for the medium\n"
        )

    def get_tools(self) -> list[str]:
        return ["text_transform", "json_parse", "read_file"]


class AnalystSkill(SkillPlugin):
    """Data analysis skill - specialized in analyzing data and generating insights.

    Tools typically used: calc, percentage, text_transform
    """

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(
            config=config or {},
            capabilities={SKILL_EXECUTE, SKILL_GET_PROMPT, SKILL_GET_TOOLS},
        )
        self._detail_level = self.config.get("detail_level", "medium")

    async def execute(self, context: Any) -> Any:
        """Execute analysis task."""
        return {"status": "ready", "skill": "analyst"}

    def get_system_prompt(self, context: Any | None = None) -> str:
        return (
            "You are a data analysis specialist. Your role is to analyze data, "
            "identify patterns, and generate actionable insights.\n\n"
            f"Detail level: {self._detail_level}\n\n"
            "Guidelines:\n"
            "- Start with data quality assessment\n"
            "- Use appropriate analytical methods\n"
            "- Visualize data when helpful\n"
            "- Highlight key findings\n"
            "- Provide context and caveats\n"
            "- Make data-driven recommendations\n"
        )

    def get_tools(self) -> list[str]:
        return ["calc", "percentage", "min_max", "text_transform", "json_parse"]


class AssistantSkill(SkillPlugin):
    """General assistant skill - helpful, general-purpose responses.

    This is a versatile skill suitable for general conversation and tasks.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(
            config=config or {},
            capabilities={SKILL_EXECUTE, SKILL_GET_PROMPT, SKILL_GET_TOOLS},
        )
        self._personality = self.config.get("personality", "helpful")

    async def execute(self, context: Any) -> Any:
        """Execute assistant task."""
        return {"status": "ready", "skill": "assistant"}

    def get_system_prompt(self, context: Any | None = None) -> str:
        return (
            "You are a helpful AI assistant. Your role is to assist users "
            "with a wide variety of tasks.\n\n"
            f"Personality: {self._personality}\n\n"
            "Guidelines:\n"
            "- Be helpful, honest, and harmless\n"
            "- Ask clarifying questions when needed\n"
            "- Admit when you don't know something\n"
            "- Provide accurate information\n"
            "- Respect user privacy\n"
            "- Be patient and polite\n"
        )

    def get_tools(self) -> list[str]:
        # Assistant can use any tool as needed
        return []  # All tools available
