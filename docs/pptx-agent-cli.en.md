# pptx-agent CLI Guide

## Install

```bash
uv add "io-openagent-sdk[pptx]"
```

System dependencies: Python ≥3.10, Node.js ≥18, npm, `markitdown` (Python package). The CLI's environment doctor detects missing pieces on first run and walks you through installing them.

## Commands

- `pptx-agent new [--topic "..."] [--slug ...]` — start a new deck.
- `pptx-agent resume <slug>` — resume an interrupted deck.
- `pptx-agent memory list [--section ...]` — list stored preferences.
- `pptx-agent memory forget <entry_id>` — remove one preference.
- `pptx-agent memory --section ...` — legacy shorthand for `memory list --section ...`.

## 7-stage pipeline and interactions

1. **Intent Analysis** — the LLM turns your free-form description into an `IntentReport`. The wizard shows every field and lets you choose `confirm / edit field / regenerate / abort`. Selecting `edit field` lets you edit any of `topic / audience / purpose / tone / slide_count_hint / language / required_sections / visuals_hint / research_queries`; list fields offer `add / remove / reorder / edit-item`. After confirming you can opt-in to persist the result as a `user_goals` preference.
2. **Environment Check** — validates Python / Node / npm / markitdown / API keys. Missing pieces get an interactive fix (secrets use the password prompt and write to the user-level `.env`).
3. **Research** — calls Tavily (MCP first, REST fallback) and renders every source for multi-select. On confirm you can save the kept sources as a `references` preference.
4. **Outline** — generates a slide-by-slide outline with a menu: `accept / add slide / remove slide / reorder slides / edit slide / regenerate all / abort`. Indexes re-compact after every mutation; `regenerate all` asks before discarding local edits.
5. **Theme** — the agent returns 3–5 candidates; the wizard renders them side-by-side in Rich `Columns` (5 palette swatches + font pairing + style + badge). Menu: `pick 1..N / regenerate / custom editor / abort`. The custom editor validates hex input (strips a leading `#`) and seeds from the first candidate. Accepted themes can be saved as a `decisions` preference.
6. **Slide Generation** — each slide runs as its own agent call with `concurrency=3`. Returned `SlideIR` values are strictly validated against the slide-type slot schema; failures retry up to 2 times, then fall back to a `freeform` IR with a generated script. A Rich `Live` table shows per-slide state (`queued / running / retry-N / ok / fallback / failed`). After the run the summary (`N ok / M fallback / K failed`) lets you rerun any failed index.
7. **Compile + QA** — writes JS templates → `npm install` (skipped when `node_modules` already exists) → `node compile.js` → optional `markitdown` read-back.

## Resume

Project state lives in `outputs/<slug>/project.json` (atomic writes; a `project.json.bak` copy is rotated on every save). Ctrl+C at any stage flushes state and exits with code `130`; `pptx-agent resume <slug>` picks up from the last saved stage.

If `project.json` is corrupt or fails pydantic validation, the CLI surfaces the error and offers three choices:
1. Restore from `project.json.bak`.
2. Delete `project.json` and start fresh.
3. Abort.

## Keys & `.env`

- Required: `LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL`.
- Optional: `TAVILY_API_KEY` (enables research stage).
- User-level `.env`: `~/.config/pptx-agent/.env` — shared across projects.
- Project-level `.env`: `outputs/<slug>/.env` — overrides user-level.

## Memory

Cross-session memory is backed by the `MarkdownMemory` builtin, writing to `~/.config/pptx-agent/memory/`:

```
MEMORY.md          index
user_goals.md      preferences confirmed at intent stage
user_feedback.md   generic feedback rules (fallback bucket)
decisions.md       theme / slide-generation decisions
references.md      kept research sources
```

Future runs of the same agent inject these via `memory_view`, so the LLM sees your earlier preferences. Use `pptx-agent memory forget <id>` to drop any entry.
