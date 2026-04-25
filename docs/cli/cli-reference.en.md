# CLI Reference

The OpenAgents SDK ships a command-line tool `openagents` with utilities for config validation, schema export, and plugin enumeration. All subcommands are accessible through either of these forms:

```bash
openagents <subcommand> [options]
# or
python -m openagents <subcommand> [options]
```

!!! note "Invocation forms"
    Both forms are fully equivalent. In projects managed with `uv`, prefer `uv run openagents <subcommand>` to ensure the project's virtual environment is used.

---

## Subcommand Overview

| Subcommand | Description |
|------------|-------------|
| [`schema`](#schema) | Dump AppConfig or per-plugin JSON/YAML Schema |
| [`validate`](#validate) | Load and validate `agent.json` without running the agent |
| [`list-plugins`](#list-plugins) | List all registered plugins grouped by seam |

---

## `openagents schema` {#schema}

Dumps the JSON Schema for the entire `AppConfig`, or for the configuration of a specific plugin or seam. Useful for understanding the config file structure, generating documentation, or configuring JSON Schema validation in your IDE.

### Usage

```bash
openagents schema [--plugin NAME] [--seam SEAM] [--format {json,yaml}] [--out FILE]
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--plugin NAME` | string | — | Dump the config schema for a single plugin by name. If `--seam` is also specified, the search is scoped to that seam. |
| `--seam SEAM` | string | — | Restrict output to a specific seam (e.g. `context_assembler`). When used alone (without `--plugin`), dumps schemas for all plugins in that seam. |
| `--format` | `json` \| `yaml` | `json` | Output format. `yaml` requires the `[yaml]` optional extra (see below). |
| `--out FILE` | file path | — | Write output to a file instead of stdout. |

### Behavior

- **No options**: Outputs the full `AppConfig` JSON Schema (all top-level fields).
- **`--seam` only**: Outputs config schemas for all built-in plugins in that seam, structured as `{ seam: { plugin_name: schema } }`.
- **`--plugin`** (optionally with `--seam`): Outputs the config schema for the named plugin. If the plugin does not declare a `Config` inner class, the command exits with code 2.
- **`--out`**: Automatically appends a trailing newline when writing to a file.

### Examples

```bash
# Dump the full AppConfig schema (JSON, to stdout)
openagents schema

# Dump schemas for all plugins in the context_assembler seam
openagents schema --seam context_assembler

# Dump the config schema for the plugin named head_tail
openagents schema --plugin head_tail

# Look up head_tail within the context_assembler seam
openagents schema --seam context_assembler --plugin head_tail

# Dump as YAML and write to a file
openagents schema --format yaml --out schema.yaml

# Dump the full schema and write to a JSON file
openagents schema --out appconfig-schema.json
```

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `2` | Plugin not found; plugin has no config schema; or PyYAML not installed |

---

## `openagents validate` {#validate}

Loads and validates an `agent.json` config file without starting any agent or making network calls. Suitable for use in CI pipelines as a pre-flight check for configuration files.

### Usage

```bash
openagents validate <path> [--strict] [--show-resolved]
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `path` | positional (required) | — | Path to the `agent.json` file to validate. |
| `--strict` | flag | `false` | Strict mode: additionally verify that every `type` field resolves to a registered built-in plugin. Covers seams: `memory`, `pattern`, `tool_executor`, `context_assembler`. |
| `--show-resolved` | flag | `false` | After successful validation, print the fully-resolved `AppConfig` as JSON to stdout. |

### Behavior

The command loads the config via `load_config(path)` and catches these error types, exiting with code 2 on failure:

- `ConfigLoadError`: File not found or cannot be parsed
- `ConfigValidationError`: Pydantic validation failed (wrong field types, missing required fields, etc.)
- `ConfigError`: Other configuration errors

On success, a summary line is printed:

```
OK: agent.json is valid (2 agents, 3 seams configured)
```

With `--strict`, the command additionally checks that the `type` value of `memory`, `pattern`, `tool_executor`, and `context_assembler` in each agent config resolves to a known entry in the built-in registry. Plugins that use `impl` (a Python dotted path) are skipped by this check.

!!! warning "Decorator-registered plugins"
    `--strict` only checks the **built-in registry** (`builtin` source). Plugins registered via decorators like `@context_assembler` must be imported before the validation script runs. If their module is not imported, strict mode may falsely report them as unresolved.

### Examples

```bash
# Basic validation
openagents validate agent.json

# Strict-mode validation (verify all type fields resolve)
openagents validate agent.json --strict

# Validate and print the fully-resolved config
openagents validate agent.json --show-resolved

# Use in CI (leverage exit codes)
openagents validate agent.json --strict && echo "Config OK"
```

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Validation passed |
| `2` | File could not be loaded; schema validation failed; or unresolved plugin `type` in strict mode |

---

## `openagents list-plugins` {#list-plugins}

Lists all registered plugins, grouped by seam. Shows each plugin's source (built-in vs decorator-registered), implementation path, and whether it declares a config schema.

### Usage

```bash
openagents list-plugins [--seam SEAM] [--source {builtin,decorator,all}] [--format {table,json}]
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--seam SEAM` | string | — | Only list plugins for the specified seam. Valid values: `memory`, `pattern`, `tool`, `tool_executor`, `context_assembler`, `runtime`, `session`, `events`. |
| `--source` | `builtin` \| `decorator` \| `all` | `all` | Filter by registration source. `builtin` = built-in registry; `decorator` = plugins registered via decorators (`@tool`, `@memory`, etc.); `all` = both. |
| `--format` | `table` \| `json` | `table` | Output format. `json` produces a full-field array suitable for script consumption. |

### Output Fields

| Field | Description |
|-------|-------------|
| `seam` | The seam name this plugin belongs to |
| `name` | The plugin's registered name (used as the `type` value in config files) |
| `source` | `builtin` (built-in registry) or `decorator` (registered via a decorator) |
| `has_config_schema` | Whether the plugin declares a `Config` inner class (i.e. whether it supports schema export) |

The `json` format additionally includes an `impl_path` field containing the full Python module path of the plugin class (`module.ClassName`).

### Examples

```bash
# List all registered plugins (table format)
openagents list-plugins

# Only list plugins in the context_assembler seam
openagents list-plugins --seam context_assembler

# Only list built-in plugins
openagents list-plugins --source builtin

# Output as JSON (for scripting)
openagents list-plugins --format json

# Combined: memory seam, built-in only, JSON format
openagents list-plugins --seam memory --source builtin --format json
```

### Example Table Output

```
seam              name                source    has_config_schema
----------------  ------------------  --------  -----------------
context_assembler head_tail           builtin   True
memory            noop                builtin   False
pattern           react               builtin   True
tool_executor     default             builtin   False
```

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success (even if the result is empty) |

---

## YAML Output Dependency {#yaml-extra}

`openagents schema --format yaml` requires `PyYAML`, which is bundled in the `[yaml]` optional dependency group:

=== "pip"

    ```bash
    pip install "io-openagent-sdk[yaml]"
    ```

=== "uv"

    ```bash
    uv add "io-openagent-sdk[yaml]"
    ```

If `PyYAML` is not installed and you use `--format yaml`, the command prints the following message and exits with code 2:

```
yaml output requires PyYAML; install with: pip install io-openagent-sdk[yaml]
```

---

## Related Documentation

- [Configuration Reference](../configuration/configuration.md) — Full field documentation for `agent.json`
- [Plugin Development Guide](../plugins/plugin-development.md) — How to write and register custom plugins
- [Seams & Extension Points](../architecture/seams-and-extension-points.md) — Seam responsibilities and decision tree
- [API Reference](../reference/api-reference.md) — Core types: `Runtime`, `RunRequest`, `RunResult`, and more
