# research_analyst example

Offline research agent that exercises every new builtin added in 0.3.x:

| seam | builtin | where |
|---|---|---|
| tool_executor | retry | agent.json |
| execution_policy | composite + network_allowlist + filesystem | agent.json |
| followup_resolver | rule_based | agent.json + app/followup_rules.json |
| session | jsonl_file | agent.json + ./sessions |
| events | file_logging | agent.json + ./sessions/events.ndjson |
| response_repair_policy | strict_json | agent.json |

## Run

```bash
uv run python examples/research_analyst/run_demo.py
```

No external network is required; an aiohttp stub server on 127.0.0.1 serves all web content.
