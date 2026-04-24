# multi-agent-support-example Specification

## Purpose
TBD - created by archiving change multi-agent-support-example. Update Purpose after archive.
## Requirements
### Requirement: Example directory layout

The repository SHALL contain a directory `examples/multi_agent_support/` whose contents mirror the layering of `examples/production_coding_agent/`: an `app/` subpackage holding the app-defined protocol layer, top-level `agent_mock.json` and `agent_real.json` configs, top-level `run_demo_mock.py` and `run_demo_real.py` entry points, a `README.md`, and an `__init__.py` so the package is importable as `examples.multi_agent_support`.

#### Scenario: Required files exist
- **WHEN** the repository is checked out at the commit introducing this change
- **THEN** the following paths all exist and are non-empty: `examples/multi_agent_support/__init__.py`, `examples/multi_agent_support/README.md`, `examples/multi_agent_support/agent_mock.json`, `examples/multi_agent_support/agent_real.json`, `examples/multi_agent_support/run_demo_mock.py`, `examples/multi_agent_support/run_demo_real.py`, `examples/multi_agent_support/app/__init__.py`, `examples/multi_agent_support/app/deps.py`, `examples/multi_agent_support/app/plugins.py`, `examples/multi_agent_support/app/protocol.py`

#### Scenario: Package is importable
- **WHEN** a test runs `import examples.multi_agent_support` with the repo root on `sys.path` (as `tests/conftest.py` already arranges)
- **THEN** the import succeeds with no side effects beyond module registration

### Requirement: Four-agent customer-support topology

The `agent_mock.json` and `agent_real.json` configs SHALL each define exactly four agents with ids `concierge`, `refund_specialist`, `tech_support`, `account_lookup`. The `concierge` agent MUST have at least the router-bound tools `route_to_refund`, `route_to_tech`, and `consult_account_lookup`. The `refund_specialist` MUST have at least `consult_account_lookup` and `issue_refund`. The `tech_support` MUST have at least `consult_account_lookup` and `open_ticket`. The `account_lookup` agent MUST have at least `lookup_customer` and `find_orders`.

#### Scenario: Agent ids match
- **WHEN** `AppConfig` is loaded from either `agent_mock.json` or `agent_real.json`
- **THEN** `{a.id for a in config.agents} == {"concierge", "refund_specialist", "tech_support", "account_lookup"}`

#### Scenario: Minimum tool sets present
- **WHEN** `AppConfig` is loaded from either config
- **THEN** the `concierge` agent's tool ids include `route_to_refund`, `route_to_tech`, `consult_account_lookup`; the `refund_specialist`'s tool ids include `consult_account_lookup`, `issue_refund`; the `tech_support`'s tool ids include `consult_account_lookup`, `open_ticket`; the `account_lookup`'s tool ids include `lookup_customer`, `find_orders`

### Requirement: Multi-agent block enabled with non-default session topology

Both configs SHALL set `multi_agent.enabled: true`, `multi_agent.max_delegation_depth: 3`, and a non-null `multi_agent.default_child_budget`. At least one tool in `app/plugins.py` SHALL call `router.delegate` with each of the three `session_isolation` values (`"shared"`, `"isolated"`, `"forked"`), distributed across distinct caller agents.

#### Scenario: Multi-agent block values
- **WHEN** `AppConfig` is loaded
- **THEN** `config.multi_agent.enabled is True`, `config.multi_agent.max_delegation_depth == 3`, `config.multi_agent.default_child_budget is not None`

#### Scenario: All three isolation modes exercised across the app tools
- **WHEN** source analysis inspects `examples/multi_agent_support/app/plugins.py`
- **THEN** at least one `router.delegate(...)` or `router.transfer(...)` call passes `session_isolation="shared"`, at least one passes `session_isolation="isolated"`, and at least one passes `session_isolation="forked"`, with the three calls appearing in at least two different `ToolPlugin` subclasses

### Requirement: Mock demo covers four required scenarios

`run_demo_mock.py` SHALL execute four named scenarios deterministically against the mock-provider config and print a human-readable summary for each. The scenarios are: (1) refund flow — `concierge` transfers to `refund_specialist`, which delegates to `account_lookup` with `session_isolation="shared"`, producing a `ticket` with `kind="refund"` and a parent `RunResult.metadata["handoff_from"]` equal to the specialist's child run id; (2) tech flow — `concierge` transfers to `tech_support`, which issues at least one `session_isolation="forked"` delegation whose child session id matches the `"{parent}:fork:{run_id}"` format, plus at least one other delegation with a different isolation mode, and opens a tech ticket; (3) depth-limit — the synthetic `SelfDelegateLookupTool` invoked with a `RunContext` already at `metadata[DELEGATION_DEPTH_KEY] = max_delegation_depth` raises `DelegationDepthExceededError(depth=3, limit=3)` before any child run is constructed; (4) unknown-agent — the synthetic `DelegateToMissingTool` invokes `router.delegate("does_not_exist", ...)` and `AgentNotFoundError` propagates with `.agent_id == "does_not_exist"`.

Note on "two forks": `DefaultAgentRouter._resolve_session` builds the forked child id as `"{parent_sid}:fork:{parent_run_id}"`, so multiple `forked` delegations from the same parent run collide on the in-memory session store. A single forked delegation fully exercises the spec's fork contract (snapshot copy, post-fork write isolation); the tech scenario therefore issues one forked delegation plus one with a different isolation to demonstrate mode mixing without tripping the collision.

#### Scenario: Script runs to completion offline
- **WHEN** `uv run python examples/multi_agent_support/run_demo_mock.py` is executed with no environment variables set
- **THEN** the process exits with status 0, prints a banner for each of the four scenarios, and makes no network request

#### Scenario: Each scenario asserts its outcome
- **WHEN** the mock demo module is imported as `examples.multi_agent_support.run_demo_mock` and each scenario function is invoked directly
- **THEN** each scenario function either returns a dict with the documented shape (scenarios 1 and 2) or raises the documented exception and is caught locally (scenarios 3 and 4)

### Requirement: Real LLM demo wired to MiniMax-Anthropic endpoint

`run_demo_real.py` SHALL load `agent_real.json`, read `LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL` from the environment (same convention as `examples/multi_agent/run_demo_real.py`), and drive at least the refund flow and the tech flow end-to-end through a real provider. The module MUST NOT be imported or executed by the integration test.

#### Scenario: Missing env var prints actionable error
- **WHEN** `run_demo_real.py` is executed without `LLM_API_KEY` set
- **THEN** the script exits with a non-zero status and prints a one-line message naming the missing variable

#### Scenario: Env vars satisfied — refund scenario runs
- **GIVEN** `LLM_API_KEY`, `LLM_API_BASE`, and `LLM_MODEL` are set to valid MiniMax credentials
- **WHEN** `run_demo_real.py` is invoked
- **THEN** the script drives the refund scenario through the `concierge → refund_specialist → account_lookup` path and prints the ticket draft, and drives the tech scenario end-to-end; execution does not assert specific LLM output strings

### Requirement: App-defined protocol layer, not kernel changes

All app-specific types (deps, pydantic envelopes, tool implementations) SHALL live under `examples/multi_agent_support/app/`. The change MUST NOT add, remove, or modify any file under `openagents/` or `openspec/specs/agent-router/`, and MUST NOT introduce any new `RunContext` / `RunRequest` attribute on kernel interfaces. App state MUST ride on `RunContext.state` / `.scratch` / `RunRequest.context_hints` / `RunArtifact.metadata` only.

#### Scenario: No kernel diff
- **WHEN** the PR that lands this change is inspected via `git diff`
- **THEN** there are zero modifications to files under `openagents/` and zero modifications to files under `openspec/specs/` (other than the new spec folder introduced by this change)

#### Scenario: App state lives on RunContext.state
- **WHEN** source analysis inspects `examples/multi_agent_support/app/plugins.py` and `app/protocol.py`
- **THEN** any persistence of app state between tool invocations within a run uses `ctx.state[...]` or `ctx.scratch[...]` and no tool assigns attributes directly onto `ctx` outside those dicts

### Requirement: Integration test locks regression surface

A single test module `tests/integration/test_multi_agent_support_example.py` SHALL run all four mock scenarios end-to-end against real SDK builtins (only the LLM provider is mocked) and assert the observable outcomes for each. The module MUST run under `uv run pytest -q tests/integration/test_multi_agent_support_example.py` in under 5 seconds on a developer laptop and MUST make no network calls.

#### Scenario: Refund flow assertions
- **WHEN** the refund scenario test runs
- **THEN** the parent `RunResult.stop_reason` is `StopReason.COMPLETED`, `RunResult.metadata["handoff_from"]` equals the `refund_specialist`'s child `run_id`, `RunResult.final_output` is non-empty, and `SupportDeps.ticket_store.list()` contains exactly one ticket with `kind="refund"`

#### Scenario: Tech flow fork semantics
- **WHEN** the tech scenario test runs
- **THEN** `SupportDeps.trace` contains at least one entry with `isolation="forked"` whose `child_session_id` matches the `"<parent_session_id>:fork:<parent_run_id>"` pattern; after the top-level run completes, inspecting the session manager for that child session returns the parent's messages at fork time, and any message appended to the parent session after the fork is absent from the child session snapshot returned by `session_manager.load_messages(child_sid)`

#### Scenario: Depth limit enforcement
- **WHEN** the depth scenario test invokes the synthetic self-delegation tool with `max_delegation_depth=3`
- **THEN** a `DelegationDepthExceededError` is raised with `depth == 3` and `limit == 3`, and the surfacing `RunResult.error` field (or the test's `pytest.raises` context) matches this exception type

#### Scenario: Unknown agent error
- **WHEN** the unknown-agent scenario test invokes a tool that passes `"does_not_exist"` to `router.delegate`
- **THEN** the call raises `AgentNotFoundError` whose `.agent_id` attribute equals `"does_not_exist"` before any child run starts

### Requirement: Documentation entry points

The change SHALL update `docs/examples.md` and `docs/examples.en.md` to add a section describing `multi_agent_support` with a one-paragraph summary, "when to read this" guidance, key files list, and a run command. A standalone guide `docs/multi-agent-support-example.md` and its English counterpart `docs/multi-agent-support-example.en.md` SHALL walk through the four scenarios and name which `agent-router` spec requirement each scenario exercises. `examples/multi_agent/README.md` SHALL be updated with a one-paragraph pointer to the new production-style example.

#### Scenario: docs/examples.md section present
- **WHEN** `docs/examples.md` and `docs/examples.en.md` are read after the change lands
- **THEN** each contains a top-level section titled `## examples/multi_agent_support/` (or the English equivalent) with at least the subheadings "用途"/"Purpose" (or equivalent), "关键文件"/"Key files", "运行"/"Run"

#### Scenario: Standalone guide present
- **WHEN** `docs/multi-agent-support-example.md` and `.en.md` are read
- **THEN** each file walks through the refund, tech, depth-limit, and unknown-agent scenarios, and each scenario section cross-references at least one `agent-router` spec requirement name

#### Scenario: Minimal example README updated
- **WHEN** `examples/multi_agent/README.md` is read after the change lands
- **THEN** the file contains a paragraph (within the first 30 lines) that points readers at `examples/multi_agent_support/` as the recommended production-style multi-agent reference
