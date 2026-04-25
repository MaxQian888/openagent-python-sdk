# 流式 API 深度指南

本页面是对 [API 参考](api-reference.md) 中流式 API 一节的深度补充，涵盖运作原理、完整用法示例和注意事项。

## 1. 概述

OpenAgents 的流式 API 是 **event bus 到统一 chunk 流的投影**。

runtime 内部一直通过 `AsyncEventBus` 发布事件（LLM 文本增量、工具调用开始/结束、artifact 产出等）。`run_stream()` 在幕后订阅这条事件流，把 **已声明的事件** 映射为 `RunStreamChunk` 对象，再通过异步生成器逐一返回给调用方。

**三个主要入口：**

| 入口 | 类型 | 适用场景 |
| --- | --- | --- |
| `Runtime.run_stream(*, request)` | async generator | 异步 Python 代码（首选） |
| `stream_agent_with_dict(payload, *, request)` | sync generator | 同步上下文 |
| `stream_agent_with_config(config_path, *, request)` | sync generator | 同步上下文，从文件加载 |

!!! note
    同步封装通过 `asyncio.run()` 在底层驱动 event loop，因此**不能在已运行的 event loop 中调用**（例如在 Jupyter Notebook 的 async cell 里）。

## 2. RunStreamChunkKind

每个 chunk 携带 `kind` 字段，表示它来自哪个底层事件。

| Kind | 事件来源（event bus） | payload 关键字段 |
| --- | --- | --- |
| `run.started` | `run.started` | — |
| `llm.delta` | `llm.delta` | `text: str` |
| `llm.finished` | `llm.succeeded` | `model: str` |
| `tool.started` | `tool.called` | `tool_id: str`, `params: dict` |
| `tool.delta` | `tool.delta` | `tool_id: str`, `text: str` |
| `tool.finished` | `tool.succeeded` / `tool.failed` | `tool_id: str`, `result: Any`（成功）或 `error: str`（失败） |
| `artifact` | `artifact.emitted` | `name: str`, `kind: str`, `payload: Any` |
| `validation.retry` | `validation.retry` | `attempt: int`, `error: str` |
| `run.finished` | — （由 runtime 合成） | `result: RunResult`（通过 `.result` 字段，不在 payload 里） |

!!! note "事件过滤"
    只有 `EVENT_TO_CHUNK_KIND` 映射表中列出的事件会产生 chunk。
    其他内部事件（如 `config.reloaded`、`agent.reloaded`）不会出现在流中。

## 3. RunStreamChunk 字段

```python
class RunStreamChunk(BaseModel):
    kind: RunStreamChunkKind        # chunk 类型
    run_id: str                     # 对应 RunRequest.run_id
    session_id: str                 # 所属 session
    agent_id: str                   # 所属 agent
    sequence: int                   # 单次 run 内单调递增
    timestamp_ms: int               # Unix 毫秒时间戳
    payload: dict[str, Any]         # 事件特定数据
    result: RunResult | None        # 仅 RUN_FINISHED 携带
```

**`sequence` 字段**：在单次 run 内保证从 1 开始单调递增，每个产出的 chunk 递增一次。消费者可通过序号跳跃检测断连。  
**`result` 字段**：只在 `kind == RUN_FINISHED` 时非 `None`，携带完整的 `RunResult`（含 usage、artifacts、stop_reason 等）。

## 4. 基本用法（异步）

```python
import asyncio
from openagents import Runtime
from openagents.interfaces.runtime import RunRequest, RunStreamChunkKind

runtime = Runtime.from_config("agent.json")

async def stream_run():
    request = RunRequest(
        agent_id="assistant",
        session_id="session-1",
        input_text="请用一句话解释量子纠缠。",
    )
    async for chunk in runtime.run_stream(request=request):
        if chunk.kind is RunStreamChunkKind.LLM_DELTA:
            # 逐字打印 LLM 输出
            print(chunk.payload.get("text", ""), end="", flush=True)

        elif chunk.kind is RunStreamChunkKind.TOOL_STARTED:
            print(f"\n[工具调用] {chunk.payload.get('tool_id')}")

        elif chunk.kind is RunStreamChunkKind.TOOL_FINISHED:
            if "error" in chunk.payload:
                print(f"\n[工具失败] {chunk.payload['error']}")
            else:
                print(f"\n[工具完成] {chunk.payload.get('tool_id')}")

        elif chunk.kind is RunStreamChunkKind.ARTIFACT:
            name = chunk.payload.get("name")
            print(f"\n[Artifact] {name}")

        elif chunk.kind is RunStreamChunkKind.RUN_FINISHED:
            print(f"\n[完成] stop_reason={chunk.result.stop_reason}")
            print(f"       cost_usd={chunk.result.usage.cost_usd}")

asyncio.run(stream_run())
```

## 5. 同步用法

对于不能使用 `async` 的场景（如 CLI 脚本、WSGI 框架），使用同步封装：

```python
from openagents.runtime.sync import stream_agent_with_dict
from openagents.interfaces.runtime import RunRequest, RunStreamChunkKind

config = {
    "agents": [{
        "id": "assistant",
        "name": "Assistant",
        "memory": {"type": "noop"},
        "pattern": {"type": "react"},
    }],
    "runtime": {"type": "default"},
    "session": {"type": "in_memory"},
    "events": {"type": "async"},
    "skills": {"type": "local"},
}

request = RunRequest(
    agent_id="assistant",
    session_id="s1",
    input_text="Hello",
)

for chunk in stream_agent_with_dict(config, request=request):
    if chunk.kind is RunStreamChunkKind.LLM_DELTA:
        print(chunk.payload.get("text", ""), end="", flush=True)
    elif chunk.kind is RunStreamChunkKind.RUN_FINISHED:
        print()
        print(f"完成：{chunk.result.final_output}")
```

从文件加载：

```python
from openagents.runtime.sync import stream_agent_with_config
from openagents.interfaces.runtime import RunRequest, RunStreamChunkKind

request = RunRequest(
    agent_id="assistant",
    session_id="s1",
    input_text="Hello",
)

for chunk in stream_agent_with_config("agent.json", request=request):
    if chunk.kind is RunStreamChunkKind.LLM_DELTA:
        print(chunk.payload.get("text", ""), end="", flush=True)
```

## 6. 结合结构化输出（校验重试）

当 `RunRequest.output_type` 被设置时，校验失败会产生 `VALIDATION_RETRY` chunk，之后 runtime 重新进入 `pattern.execute()`，再次产出一组新的 LLM/tool chunk。

```python
from pydantic import BaseModel
from openagents.interfaces.runtime import RunRequest, RunBudget, RunStreamChunkKind

class Summary(BaseModel):
    title: str
    points: list[str]

request = RunRequest(
    agent_id="assistant",
    session_id="s1",
    input_text="总结以下内容：...",
    output_type=Summary,
    budget=RunBudget(max_validation_retries=3),
)

async for chunk in runtime.run_stream(request=request):
    if chunk.kind is RunStreamChunkKind.VALIDATION_RETRY:
        attempt = chunk.payload.get("attempt", "?")
        error = chunk.payload.get("error", "")
        print(f"\n[校验重试 #{attempt}] {error}")

    elif chunk.kind is RunStreamChunkKind.LLM_DELTA:
        print(chunk.payload.get("text", ""), end="", flush=True)

    elif chunk.kind is RunStreamChunkKind.RUN_FINISHED:
        result = chunk.result
        if result.final_output is not None:
            summary: Summary = result.final_output
            print(f"\n标题：{summary.title}")
        elif result.error:
            print(f"\n失败：{result.error}")
```

用 `attempt` 字段区分不同轮次的重试：每次重试会产出一个新的 `VALIDATION_RETRY` chunk，其后跟着该轮的完整 LLM/tool chunk 序列。

## 7. 多 Agent 并发流

在并发执行多个 agent 时，使用 `run_id` 区分各 run 的 chunk：

```python
import asyncio
from openagents.interfaces.runtime import RunRequest, RunStreamChunkKind
from uuid import uuid4

async def stream_multiple():
    requests = [
        RunRequest(agent_id="assistant", session_id=f"s{i}",
                   input_text=f"任务 {i}", run_id=str(uuid4()))
        for i in range(3)
    ]

    async def consume(req):
        chunks = []
        async for chunk in runtime.run_stream(request=req):
            chunks.append(chunk)
        return req.run_id, chunks

    results = await asyncio.gather(*[consume(r) for r in requests])
    for run_id, chunks in results:
        finished = next(c for c in chunks if c.kind is RunStreamChunkKind.RUN_FINISHED)
        print(f"run={run_id[:8]}  output={finished.result.final_output}")

asyncio.run(stream_multiple())
```

!!! tip
    `sequence` 是 **per-run** 的，不是 per-session 的。多个 run 并发时，相同 sequence 值可能来自不同 run——使用 `run_id` 而不是 `sequence` 来关联 chunk。

## 8. 实现原理

```
run_stream()
  │
  ├─ subscribe("*", handler)          # 通配符订阅 event bus
  │
  ├─ asyncio.create_task(_drive_run)  # 后台运行 run_detailed()
  │
  └─ 轮询 queue，yield RunStreamChunk
       │
       ├─ llm.delta → LLM_DELTA
       ├─ llm.succeeded → LLM_FINISHED
       ├─ tool.called → TOOL_STARTED
       ├─ tool.delta → TOOL_DELTA
       ├─ tool.succeeded / tool.failed → TOOL_FINISHED
       ├─ artifact.emitted → ARTIFACT
       ├─ validation.retry → VALIDATION_RETRY
       └─ [run task 完成] → RUN_FINISHED（合成，不来自 event bus）
```

**关键细节：**

1. **事件过滤**：`project_event()` 查询 `EVENT_TO_CHUNK_KIND` 映射表，未映射的事件静默丢弃。
2. **run_id 过滤**：payload 中含有 `run_id` 且与当前 run 不匹配的事件会被跳过，防止同 session 内的其他并发 run 干扰当前流。
3. **RUN_FINISHED 合成**：terminal chunk 由 `run_stream()` 在 run task 完成后手动合成，不依赖 event bus，确保即使 run 失败也能收到终结 chunk。
4. **取消安全**：生成器的 `finally` 块会取消 run task 并尝试从订阅列表中移除 handler，防止泄漏。

## 9. 注意事项

!!! warning "不能在运行中的 event loop 里调用同步封装"
    `stream_agent_with_dict` / `stream_agent_with_config` 使用 `asyncio.run()`，
    不能在已有 event loop 的环境（如 Jupyter、FastAPI 的 async handler）中调用。
    在这些场景中请直接使用 `runtime.run_stream()`。

!!! warning "tool.finished 同时对应成功和失败"
    `TOOL_FINISHED` chunk 由 `tool.succeeded` 和 `tool.failed` 两个事件共同映射。
    消费者应检查 `payload.get("error")` 来区分结果，而不是假设 `TOOL_FINISHED` 必然成功。

!!! tip "断连检测"
    如果你在 WebSocket 或 SSE 传输层上转发 chunk，建议在每个 chunk 中包含 `sequence` 字段。
    客户端发现序号不连续时，可以重新请求从断点处恢复（前提是你在服务端做了 chunk 缓存）。

!!! note "RUN_FINISHED 保证最后发出"
    即使 run 内部发生异常，`run_stream()` 也**始终**在最后产出一个 `RUN_FINISHED` chunk，
    其 `result.stop_reason` 为 `failed`，`result.error` 包含错误信息。
    消费者可以无条件地以 `RUN_FINISHED` 作为流结束的信号。

## 继续阅读

- [API 参考](api-reference.md)
- [配置参考](../configuration/configuration.md)
- [插件开发](../plugins/plugin-development.md)
- [Seam 与扩展点](../architecture/seams-and-extension-points.md)
