## ADDED Requirements

### Requirement: `openagents tools` is a registered top-level subcommand

`openagents/cli/commands/tools.py` SHALL be added to the `COMMANDS` registry in `openagents/cli/commands/__init__.py`. The command SHALL use nested subparsers for its `list` and `call` sub-actions. Invoking `openagents tools` without a sub-action SHALL print usage help to stderr and exit `1`.

#### Scenario: `openagents tools --help` lists sub-actions

- **WHEN** `openagents tools --help` is invoked
- **THEN** help text includes `list` and `call` as available sub-actions

#### Scenario: `openagents tools` without sub-action exits 1

- **WHEN** `openagents tools` is invoked without `list` or `call`
- **THEN** the process exits `1` and stderr includes usage guidance

---

### Requirement: `openagents tools list` enumerates registered tools for an agent

`openagents tools list --config <path> [--agent <id>] [--format text|json]` SHALL:
1. Load the config via `load_config(path)`.
2. Select the agent (same `_select_agent` logic as `run`/`chat`; single-agent configs auto-select).
3. For each tool ref in `agent.tools`:
   - Read `id` and `type` from the config.
   - Attempt to resolve and instantiate the tool plugin via the plugin loader to extract `description` and parameter schema summary. If instantiation fails, display `(schema unavailable: <reason>)` in place of those fields.
4. Output:
   - `text` (default): aligned columns `id | type | description | params`.
   - `json`: JSON array `[{"id", "type", "description", "params_schema", "error"}]`.
5. Exit `0` if the config loads; exit `2` on `ConfigError`.

The command SHALL NOT start a full Runtime (no session backend, no event bus, no pattern).

#### Scenario: Lists tools from single-agent config

- **WHEN** `openagents tools list --config agent.json` is invoked on a config with 2 tools
- **THEN** output contains 2 rows and exit code is `0`

#### Scenario: JSON format is valid parseable output

- **WHEN** `openagents tools list --config agent.json --format json` is invoked
- **THEN** stdout is a valid JSON array that can be parsed by `json.loads`

#### Scenario: Tool with unresolvable impl shows graceful error

- **WHEN** a tool ref has `"impl": "nonexistent.module.MyTool"` that cannot be imported
- **THEN** the row still appears with `"error": "(schema unavailable: ...)"` and exit code is `0`

#### Scenario: Multi-agent config requires --agent

- **WHEN** `openagents tools list --config multi.json` is invoked on a config with 2 agents and no `--agent` flag
- **THEN** the process exits `1` and stderr names both agents

#### Scenario: No tools registered prints informative message

- **WHEN** the selected agent has an empty `tools` list
- **THEN** stdout (text mode) contains `(no tools registered for agent <id>)` and exit code is `0`

---

### Requirement: `openagents tools call` invokes a single tool directly

`openagents tools call --config <path> <tool_id> [JSON_ARGS] [--agent <id>] [--format text|json]` SHALL:
1. Load config and select agent as above.
2. Verify that `<tool_id>` is declared in `agent.tools`; if not, exit `1` with the valid tool ids listed.
3. Construct `Runtime.from_config(path)` to ensure the tool executor is wired.
4. Execute the tool via the runtime's `tool_executor` using a `ToolExecutionRequest(tool_id=tool_id, params=json.loads(JSON_ARGS or "{}"))`.
5. Print the result:
   - `text`: `_render_value`-style pretty-print (JSON-aware).
   - `json`: raw JSON of the result.
6. Exit `0` on success; exit `3` on tool execution failure; exit `1` on JSON parse error in `JSON_ARGS`.

`JSON_ARGS` is an optional positional argument; omitting it is equivalent to passing `"{}"`.

#### Scenario: Successful tool call prints result

- **WHEN** `openagents tools call --config agent.json my_tool '{"input": "hello"}'` is invoked and the tool succeeds
- **THEN** stdout contains the tool result and exit code is `0`

#### Scenario: Unknown tool_id exits 1

- **WHEN** `<tool_id>` is not in the agent's tools list
- **THEN** the process exits `1` and stderr lists the valid tool ids

#### Scenario: Tool execution failure exits 3

- **WHEN** the tool raises an exception during execution
- **THEN** the process exits `3` and stderr contains the exception type and message

#### Scenario: Invalid JSON_ARGS exits 1

- **WHEN** `JSON_ARGS` is `"not json"`
- **THEN** the process exits `1` and stderr indicates a JSON parse error

#### Scenario: Omitting JSON_ARGS defaults to empty params

- **WHEN** `openagents tools call --config agent.json my_tool` is invoked without `JSON_ARGS`
- **THEN** the tool is called with `params={}` (no error from missing argument)

#### Scenario: JSON format output is parseable

- **WHEN** `openagents tools call --config agent.json my_tool --format json` is invoked and the tool returns a dict
- **THEN** stdout is valid JSON
