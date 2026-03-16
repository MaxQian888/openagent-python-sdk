"""Skill plugin contract.

Skill is a reusable agent behavior definition that combines:
- System prompt: How the agent should behave
- Tools: What tools the agent can use
- Configuration: Skill-specific settings
"""

from __future__ import annotations

from typing import Any

from .plugin import BasePlugin

SKILL_EXECUTE = "skill.execute"
SKILL_GET_PROMPT = "skill.get_prompt"
SKILL_GET_TOOLS = "skill.get_tools"


class SkillPlugin(BasePlugin):
    """Base skill plugin.

    Skills are reusable behavior definitions that can be composed
    to build complex agent behaviors.
    """

    async def execute(self, context: Any) -> Any:
        """Execute the skill and return result."""
        raise NotImplementedError("SkillPlugin.execute must be implemented")

    def get_system_prompt(self, context: Any | None = None) -> str:
        """Get the system prompt for this skill.

        Args:
            context: Optional execution context

        Returns:
            System prompt string
        """
        raise NotImplementedError("SkillPlugin.get_system_prompt must be implemented")

    def get_tools(self) -> list[str]:
        """Get list of tool IDs this skill requires.

        Returns:
            List of tool IDs
        """
        return []
