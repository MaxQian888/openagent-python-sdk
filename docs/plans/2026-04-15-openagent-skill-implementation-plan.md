# OpenAgent Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver one shared `openagent` agent-builder core plus two thin adapters: a Codex/Claude skill and a main-agent callable adapter.

**Architecture:** Keep `openagent-sdk` as a single-agent kernel and build a higher-level `agent builder + smoke runner` above it. Both host surfaces must call the same core modules so that schema, behavior, tests, and docs stay aligned.

**Tech Stack:** Python, pytest, existing OpenAgents runtime/config schema, repo-contained skill files

---

### Task 1: Create Core Models

**Files:**

- Create: `openagents/agent_builder/__init__.py`
- Create: `openagents/agent_builder/models.py`
- Test: `tests/unit/test_agent_builder_models.py`

- [ ] **Step 1: Write the failing model test**

```python
from openagents.agent_builder.models import OpenAgentSkillInput, OpenAgentSkillOutput


def test_openagent_skill_models_capture_v0_contract():
    payload = OpenAgentSkillInput(
        task_goal="Review a patch",
        agent_role="reviewer",
        agent_mode="team-role",
        workspace_root="C:/repo",
    )

    assert payload.task_goal == "Review a patch"
    assert payload.agent_role == "reviewer"
    assert payload.agent_mode == "team-role"
    assert payload.smoke_run is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest -q tests/unit/test_agent_builder_models.py`
Expected: FAIL with import error because `openagents.agent_builder.models` does not exist

- [ ] **Step 3: Add minimal model module**

```python
from dataclasses import dataclass, field
from typing import Any


@dataclass
class OpenAgentSkillInput:
    task_goal: str
    agent_role: str
    agent_mode: str
    workspace_root: str | None = None
    available_tools: list[str] = field(default_factory=list)
    constraints: dict[str, Any] = field(default_factory=dict)
    handoff_expectation: dict[str, Any] = field(default_factory=dict)
    overrides: dict[str, Any] = field(default_factory=dict)
    smoke_run: bool = True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest -q tests/unit/test_agent_builder_models.py`
Expected: PASS

### Task 2: Add Archetype Selection

**Files:**

- Create: `openagents/agent_builder/archetypes.py`
- Test: `tests/unit/test_agent_builder_archetypes.py`

- [ ] **Step 1: Write failing tests for archetype defaults**

```python
from openagents.agent_builder.archetypes import resolve_archetype


def test_resolve_archetype_returns_reviewer_defaults():
    archetype = resolve_archetype("reviewer")
    assert archetype["pattern"]["type"] == "react"
    assert "read_file" in archetype["tools"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest -q tests/unit/test_agent_builder_archetypes.py`
Expected: FAIL with import error

- [ ] **Step 3: Implement the minimal archetype table**

```python
ARCHETYPES = {
    "planner": {...},
    "coder": {...},
    "reviewer": {...},
    "researcher": {...},
}


def resolve_archetype(name: str) -> dict:
    try:
        return ARCHETYPES[name]
    except KeyError as exc:
        raise ValueError(f"Unknown archetype: {name}") from exc
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest -q tests/unit/test_agent_builder_archetypes.py`
Expected: PASS

### Task 3: Render Runnable Agent Spec

**Files:**

- Create: `openagents/agent_builder/render.py`
- Test: `tests/unit/test_agent_builder_render.py`

- [ ] **Step 1: Write a failing render test**

```python
from openagents.agent_builder.models import OpenAgentSkillInput
from openagents.agent_builder.render import render_agent_spec


def test_render_agent_spec_outputs_single_agent_appconfig_bundle():
    spec = render_agent_spec(
        OpenAgentSkillInput(
            task_goal="Review a patch",
            agent_role="reviewer",
            agent_mode="team-role",
        ),
        archetype={...},
    )

    assert spec["sdk_config"]["version"] == "1.0"
    assert len(spec["sdk_config"]["agents"]) == 1
    assert spec["run_request_template"]["agent_id"] == spec["agent_key"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest -q tests/unit/test_agent_builder_render.py`
Expected: FAIL with missing module/function

- [ ] **Step 3: Implement minimal render logic**

```python
def render_agent_spec(payload, archetype):
    agent_id = payload.agent_role.strip().replace(" ", "-")
    return {
        "agent_key": agent_id,
        "purpose": payload.task_goal,
        "sdk_config": {...},
        "run_request_template": {
            "agent_id": agent_id,
            "input_text": "<filled by caller>",
            "context_hints": {},
            "metadata": {},
        },
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest -q tests/unit/test_agent_builder_render.py`
Expected: PASS

### Task 4: Add Smoke Runner

**Files:**

- Create: `openagents/agent_builder/smoke.py`
- Test: `tests/unit/test_agent_builder_smoke.py`

- [ ] **Step 1: Write a failing smoke-run test**

```python
import pytest

from openagents.agent_builder.smoke import smoke_run_agent_spec


@pytest.mark.asyncio
async def test_smoke_run_agent_spec_returns_passed_result_for_valid_spec():
    result = await smoke_run_agent_spec(spec_bundle={...}, smoke_input="hello")
    assert result["status"] == "passed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest -q tests/unit/test_agent_builder_smoke.py`
Expected: FAIL because helper does not exist

- [ ] **Step 3: Implement minimal smoke runner with `Runtime.from_dict()`**

```python
async def smoke_run_agent_spec(spec_bundle: dict, smoke_input: str = "hello") -> dict:
    runtime = Runtime.from_dict(spec_bundle["sdk_config"])
    try:
        result = await runtime.run(
            agent_id=spec_bundle["run_request_template"]["agent_id"],
            session_id="openagent-skill-smoke",
            input_text=smoke_input,
        )
        return {"status": "passed", "result": result}
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}
    finally:
        await runtime.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest -q tests/unit/test_agent_builder_smoke.py`
Expected: PASS

### Task 5: Compose The Shared Builder

**Files:**

- Create: `openagents/agent_builder/builder.py`
- Test: `tests/unit/test_agent_builder_builder.py`

- [ ] **Step 1: Write a failing end-to-end builder test**

```python
import pytest

from openagents.agent_builder.builder import build_openagent_skill_output
from openagents.agent_builder.models import OpenAgentSkillInput


@pytest.mark.asyncio
async def test_build_openagent_skill_output_returns_spec_rationale_and_smoke_result():
    output = await build_openagent_skill_output(
        OpenAgentSkillInput(
            task_goal="Review a patch",
            agent_role="reviewer",
            agent_mode="team-role",
        )
    )

    assert output.agent_spec["agent_key"] == "reviewer"
    assert output.smoke_result["status"] in {"passed", "failed"}
    assert output.design_rationale
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest -q tests/unit/test_agent_builder_builder.py`
Expected: FAIL with missing builder

- [ ] **Step 3: Implement the minimal builder pipeline**

```python
async def build_openagent_skill_output(payload):
    normalized = normalize_input(payload)
    archetype = resolve_archetype(normalized.agent_role)
    spec = render_agent_spec(normalized, archetype)
    smoke = await smoke_run_agent_spec(spec) if normalized.smoke_run else {"status": "skipped"}
    return OpenAgentSkillOutput(
        agent_spec=spec,
        agent_prompt_summary="...",
        design_rationale="...",
        handoff_contract={...},
        integration_hints={...},
        smoke_result=smoke,
        next_actions=[...],
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest -q tests/unit/test_agent_builder_builder.py`
Expected: PASS

### Task 6: Add Main-Agent Adapter

**Files:**

- Create: `openagents/agent_builder/host_adapter.py`
- Test: `tests/unit/test_agent_builder_host_adapter.py`

- [ ] **Step 1: Write a failing adapter test**

```python
import pytest

from openagents.agent_builder.host_adapter import run_openagent_skill


@pytest.mark.asyncio
async def test_run_openagent_skill_wraps_shared_builder():
    result = await run_openagent_skill({"task_goal": "Review a patch", "agent_role": "reviewer", "agent_mode": "team-role"})
    assert "agent_spec" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest -q tests/unit/test_agent_builder_host_adapter.py`
Expected: FAIL with missing adapter

- [ ] **Step 3: Implement minimal adapter**

```python
async def run_openagent_skill(payload: dict) -> dict:
    input_obj = OpenAgentSkillInput(**payload)
    result = await build_openagent_skill_output(input_obj)
    return asdict(result)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest -q tests/unit/test_agent_builder_host_adapter.py`
Expected: PASS

### Task 7: Deliver Codex / Claude Skill Wrapper

**Files:**

- Create: `skills/openagent-agent-builder/SKILL.md`
- Create: `skills/openagent-agent-builder/agents/openai.yaml`
- Create: `skills/openagent-agent-builder/references/architecture.md`
- Create: `skills/openagent-agent-builder/references/examples.md`
- Test: `tests/unit/test_openagent_agent_builder_skill_artifacts.py`

- [ ] **Step 1: Write a failing artifact test**

```python
from pathlib import Path


def test_openagent_agent_builder_skill_files_exist():
    root = Path("skills/openagent-agent-builder")
    assert (root / "SKILL.md").exists()
    assert (root / "agents" / "openai.yaml").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest -q tests/unit/test_openagent_agent_builder_skill_artifacts.py`
Expected: FAIL because skill files do not exist

- [ ] **Step 3: Create the minimal skill files**

```markdown
---
name: openagent-agent-builder
description: Build one runnable OpenAgents single-agent spec and smoke test it for use as a subagent or team-role agent.
---
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest -q tests/unit/test_openagent_agent_builder_skill_artifacts.py`
Expected: PASS

### Task 8: Add Documentation And Final Verification

**Files:**

- Modify: `docs/README.md`
- Modify: `docs/examples.md`
- Create: `docs/openagent-agent-builder.md`
- Test: `tests/unit/test_openagent_agent_builder_docs.py`

- [ ] **Step 1: Document the new skill and where it sits relative to the single-agent kernel**
- [ ] **Step 2: Add docs tests for the new doc entrypoints if needed**
- [ ] **Step 3: Run `uv run pytest -q`**
- [ ] **Step 4: Run targeted smoke validation for the shared builder**
- [ ] **Step 5: Review `git diff --stat` and confirm the skill still respects the single-agent SDK boundary**
