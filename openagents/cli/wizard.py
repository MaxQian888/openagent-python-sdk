from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

try:
    from rich.console import Console
    from rich.panel import Panel
except ImportError:  # pragma: no cover
    Console = object  # type: ignore[assignment,misc]
    Panel = None  # type: ignore[assignment]

try:
    import questionary
except ImportError:  # pragma: no cover
    questionary = None  # type: ignore[assignment]


@dataclass
class StepResult:
    status: Literal["completed", "skipped", "aborted", "retry"]
    data: Any = None


class WizardStep(Protocol):
    title: str
    description: str

    async def render(self, console: Any, project: Any) -> StepResult: ...


class Wizard:
    """Drive a sequence of WizardSteps with Rich layout and optional questionary prompts.

    What:
        Iterates ``steps`` in order, calling ``render(console, project)`` on
        each and branching on the returned :class:`StepResult`. ``resume``
        starts from a named step. UI helpers (``panel``, ``confirm``,
        ``select``, ``multi_select``, ``password``, ``text``) wrap Rich
        and questionary so steps don't import them directly.
    """

    def __init__(
        self,
        steps: list[WizardStep],
        project: Any,
        layout: Literal["sidebar", "linear"] = "sidebar",
        console: Any = None,
    ):
        self._steps = list(steps)
        self._project = project
        self._layout = layout
        self._console = console or (Console() if Console is not object else None)

    async def run(self, max_retries_per_step: int = 20) -> Literal["completed", "aborted"]:
        i = 0
        while i < len(self._steps):
            step = self._steps[i]
            retries = 0
            while True:
                result = await step.render(self._console, self._project)
                if result.status == "aborted":
                    return "aborted"
                if result.status == "retry":
                    retries += 1
                    if retries >= max_retries_per_step:
                        return "aborted"
                    continue
                break
            i += 1
        return "completed"

    async def resume(self, from_step: str, max_retries_per_step: int = 20) -> Literal["completed", "aborted"]:
        for i, step in enumerate(self._steps):
            if getattr(step, "title", None) == from_step:
                steps_local = self._steps[i:]
                saved = self._steps
                self._steps = steps_local
                try:
                    return await self.run(max_retries_per_step=max_retries_per_step)
                finally:
                    self._steps = saved
        raise ValueError(f"No step with title {from_step!r}")

    # ---- UI helpers (thin; easy to mock in tests) -------------------
    @staticmethod
    def panel(title: str, body: str) -> Any:
        return Panel(body, title=title) if Panel is not None else None

    @staticmethod
    async def confirm(prompt: str, default: bool = True) -> bool:
        if questionary is None:
            return default
        return bool(await questionary.confirm(prompt, default=default).ask_async())

    @staticmethod
    async def select(prompt: str, choices: list[str], default: str | None = None) -> str:
        if questionary is None:
            return default or choices[0]
        return str(await questionary.select(prompt, choices=choices, default=default).ask_async())

    @staticmethod
    async def multi_select(prompt: str, choices: list[str], min_selected: int = 0) -> list[str]:
        if questionary is None:
            return list(choices) if min_selected else []
        picked = await questionary.checkbox(prompt, choices=choices).ask_async()
        return list(picked or [])

    @staticmethod
    async def password(prompt: str) -> str:
        if questionary is None:
            return ""
        return str(await questionary.password(prompt).ask_async() or "")

    @staticmethod
    async def text(prompt: str, default: str | None = None) -> str:
        if questionary is None:
            return default or ""
        return str(await questionary.text(prompt, default=default or "").ask_async() or "")
