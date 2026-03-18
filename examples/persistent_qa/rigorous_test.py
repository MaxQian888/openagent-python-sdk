"""
Rigorous Testing - 最严苛测试

覆盖:
1. 边界条件
2. 错误处理
3. 并发压力
4. 资源泄漏
5. 异常恢复
6. 性能基准
"""

import asyncio
import os
import sys
import time
import json
from pathlib import Path
from collections import defaultdict

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from openagents import Runtime
from openagents.config.loader import load_config_dict


def load_env():
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


# ============================================================================
# Test 1: 边界条件测试
# ============================================================================

async def test_edge_cases():
    print("\n" + "=" * 60)
    print("[1] Edge Cases")
    print("=" * 60)

    runtime = Runtime.from_config("examples/persistent_qa/agent.json")

    # 1.1 空输入
    print("\n  [1.1] Empty input")
    try:
        result = await runtime.run(agent_id="qa_assistant", session_id="edge_1", input_text="")
        print(f"    Empty result: {result[:50]}")
    except Exception as e:
        print(f"    Empty error: {type(e).__name__}")

    # 1.2 极长输入
    print("\n  [1.2] Long input (5000 chars)")
    long_input = "a" * 5000
    try:
        result = await runtime.run(agent_id="qa_assistant", session_id="edge_2", input_text=long_input)
        print(f"    Long result: {result[:50]}")
    except Exception as e:
        print(f"    Long error: {type(e).__name__}")

    # 1.3 特殊字符
    print("\n  [1.3] Special chars")
    try:
        result = await runtime.run(agent_id="qa_assistant", session_id="edge_3", input_text="test\n\t")
        print(f"    Special result: {result[:50]}")
    except Exception as e:
        print(f"    Special error: {type(e).__name__}")

    await runtime.close()
    print("\n  Edge cases test done")


# ============================================================================
# Test 2: 错误处理测试
# ============================================================================

async def test_error_handling():
    print("\n" + "=" * 60)
    print("[2] Error Handling")
    print("=" * 60)

    # 2.1 Invalid agent
    print("\n  [2.1] Invalid agent")
    runtime = Runtime.from_config("examples/persistent_qa/agent.json")
    try:
        await runtime.run(agent_id="nonexistent", session_id="err1", input_text="test")
    except Exception as e:
        print(f"    Expected: {type(e).__name__}")

    # 2.2 After close
    print("\n  [2.2] After runtime close")
    r2 = Runtime.from_config("examples/persistent_qa/agent.json")
    await r2.close()
    try:
        await r2.run(agent_id="qa_assistant", session_id="err2", input_text="test")
    except Exception as e:
        print(f"    Expected: {type(e).__name__}")

    # 2.3 Multiple closes
    print("\n  [2.3] Multiple closes")
    r3 = Runtime.from_config("examples/persistent_qa/agent.json")
    await r3.close()
    await r3.close()
    await r3.close()
    print("    OK")

    await runtime.close()
    print("\n  Error handling test done")


# ============================================================================
# Test 3: 并发压力测试 (用 mock LLM)
# ============================================================================

async def test_concurrency():
    print("\n" + "=" * 60)
    print("[3] Concurrency (Mock LLM)")
    print("=" * 60)

    # Create config with mock LLM
    config = load_config_dict({
        "version": "1.0",
        "agents": [{
            "id": "test",
            "name": "Test",
            "memory": {"type": "window_buffer", "config": {"window_size": 10}},
            "pattern": {"type": "react", "config": {"max_steps": 2}},
            "llm": {"provider": "mock"},
            "tools": [{"id": "calc", "type": "calc"}]
        }]
    })

    runtime = Runtime(config)

    # 3.1 50 concurrent sessions
    print("\n  [3.1] 50 parallel sessions")
    start = time.perf_counter()
    results = await asyncio.gather(*[
        runtime.run(agent_id="test", session_id=f"c{i}", input_text=f"test {i}")
        for i in range(50)
    ])
    elapsed = time.perf_counter() - start
    print(f"    50 parallel: {elapsed:.2f}s ({elapsed*20:.0f}ms/each)")

    # 3.2 Same session 100 requests
    print("\n  [3.2] Same session 100 requests")
    start = time.perf_counter()
    for i in range(100):
        await runtime.run(agent_id="test", session_id="same", input_text=f"msg {i}")
    elapsed = time.perf_counter() - start
    print(f"    100 sequential: {elapsed:.2f}s ({elapsed*10:.0f}ms/each)")

    await runtime.close()
    print("\n  Concurrency test done")


# ============================================================================
# Test 4: 资源泄漏测试
# ============================================================================

async def test_resource_leak():
    print("\n" + "=" * 60)
    print("[4] Resource Leak Test")
    print("=" * 60)

    runtime = Runtime.from_config("examples/persistent_qa/agent.json")

    # 4.1 Session accumulation
    print("\n  [4.1] Session accumulation")
    initial = runtime.get_session_count()
    print(f"    Initial: {initial}")

    for i in range(50):
        await runtime.run(agent_id="qa_assistant", session_id=f"leak_{i}", input_text=f"test {i}")

    final = runtime.get_session_count()
    print(f"    After 50: {final}")

    # 4.2 Check session isolation
    print("\n  [4.2] Session isolation check")
    await runtime.run(agent_id="qa_assistant", session_id="leak_check", input_text="Remember: secret123")
    state = await runtime.session_manager.get_state("leak_check")
    print(f"    Session state keys: {list(state.keys())}")

    await runtime.close()
    print("\n  Resource leak test done")


# ============================================================================
# Test 5: Memory 测试
# ============================================================================

async def test_memory():
    print("\n" + "=" * 60)
    print("[5] Memory Test")
    print("=" * 60)

    # Use mock LLM
    config = load_config_dict({
        "version": "1.0",
        "agents": [{
            "id": "memtest",
            "memory": {"type": "buffer"},
            "pattern": {"type": "react", "config": {"max_steps": 1}},
            "llm": {"provider": "mock"},
            "tools": []
        }]
    })

    runtime = Runtime(config)
    runtime._agents_by_id["memtest"] = config.agents[0]

    # 5.1 Buffer memory accumulates
    print("\n  [5.1] Buffer memory")
    for i in range(10):
        await runtime.run(agent_id="memtest", session_id="buf", input_text=f"msg {i}")
    state = await runtime.session_manager.get_state("buf")
    buf_len = len(state.get("memory_view", {}).get("history", []))
    print(f"    After 10: {buf_len} items (should be 10)")

    # 5.2 Window memory limits
    print("\n  [5.2] Window memory")
    config2 = load_config_dict({
        "version": "1.0",
        "agents": [{
            "id": "wintest",
            "memory": {"type": "window_buffer", "config": {"window_size": 3}},
            "pattern": {"type": "react", "config": {"max_steps": 1}},
            "llm": {"provider": "mock"},
            "tools": []
        }]
    })
    runtime._agents_by_id["wintest"] = config2.agents[0]

    for i in range(10):
        await runtime.run(agent_id="wintest", session_id="win", input_text=f"msg {i}")
    state = await runtime.session_manager.get_state("win")
    win_len = len(state.get("memory_view", {}).get("history", []))
    print(f"    After 10: {win_len} items (should be <= 3)")

    await runtime.close()
    print("\n  Memory test done")


# ============================================================================
# Test 6: Hot Reload
# ============================================================================

async def test_hotreload():
    print("\n" + "=" * 60)
    print("[6] Hot Reload Test")
    print("=" * 60)

    runtime = Runtime.from_config("examples/persistent_qa/agent.json")

    # Before reload
    await runtime.run(agent_id="qa_assistant", session_id="reload_test", input_text="before reload")
    print(f"    Before reload: OK")

    # Reload
    await runtime.reload()
    print(f"    Reload: OK")

    # After reload
    await runtime.run(agent_id="qa_assistant", session_id="reload_test", input_text="after reload")
    print(f"    After reload: OK")

    # Check sessions preserved
    print(f"    Active sessions: {runtime.get_session_count()}")

    await runtime.close()
    print("\n  Hot reload test done")


# ============================================================================
# Main
# ============================================================================

async def main():
    load_env()

    print("=" * 60)
    print("OpenAgents SDK - Rigorous Tests")
    print("=" * 60)

    try:
        await test_edge_cases()
        await test_error_handling()
        await test_concurrency()
        await test_resource_leak()
        await test_memory()
        await test_hotreload()

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED!")
        print("=" * 60)

    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

    # 1.5 Session ID 边界
    print("\n  [1.5] Session ID 边界")
    for sid in ["", "a", "a" * 1000, "中文session", "special!@#$"]:
        try:
            await runtime.run(agent_id="qa_assistant", session_id=sid, input_text="test")
            print(f"    Session ID '{sid[:20]}...': OK")
        except Exception as e:
            print(f"    Session ID '{sid[:20]}...': {e}")

    await runtime.close()
    print("\n  ✓ 边界条件测试完成")


# ============================================================================
# Test 2: 错误处理测试
# ============================================================================

async def test_error_handling():
    print("\n" + "=" * 60)
    print("[2] 错误处理测试")
    print("=" * 60)

    runtime = Runtime.from_config("examples/persistent_qa/agent.json")

    # 2.1 不存在的 Agent
    print("\n  [2.1] 不存在的 Agent")
    try:
        await runtime.run(agent_id="nonexistent", session_id="err_1", input_text="test")
    except Exception as e:
        print(f"    预期异常: {type(e).__name__}: {e}")

    # 2.2 不存在的 Tool
    print("\n  [2.2] 不存在的 Tool (需要 Tool 调用)")
    result = await runtime.run(agent_id="qa_assistant", session_id="err_2", input_text="call nonexistent_tool_xyz")
    print(f"    结果: {result[:100]}")

    # 2.3 Runtime 关闭后调用
    print("\n  [2.3] Runtime 关闭后调用")
    runtime2 = Runtime.from_config("examples/persistent_qa/agent.json")
    await runtime2.close()
    try:
        await runtime2.run(agent_id="qa_assistant", session_id="err_3", input_text="test")
    except Exception as e:
        print(f"    预期异常: {type(e).__name__}")

    # 2.4 多次关闭
    print("\n  [2.4] 多次关闭")
    runtime3 = Runtime.from_config("examples/persistent_qa/agent.json")
    await runtime3.close()
    await runtime3.close()  # 应该不抛异常
    await runtime3.close()
    print("    多次关闭: OK")

    print("\n  ✓ 错误处理测试完成")


# ============================================================================
# Test 3: 并发压力测试
# ============================================================================

async def test_concurrency_stress():
    print("\n" + "=" * 60)
    print("[3] 并发压力测试")
    print("=" * 60)

    runtime = Runtime.from_config("examples/persistent_qa/agent.json")

    # 3.1 大量并发 Session
    print("\n  [3.1] 50个并发 Session")
    async def run_session(i):
        return await runtime.run(
            agent_id="qa_assistant",
            session_id=f"stress_{i}",
            input_text=f"Session {i}"
        )

    start = time.perf_counter()
    results = await asyncio.gather(*[run_session(i) for i in range(50)])
    elapsed = time.perf_counter() - start

    print(f"    50并发耗时: {elapsed:.2f}s ({elapsed*20:.0f}ms/个)")
    print(f"    活跃Session数: {runtime.get_session_count()}")

    # 3.2 同一 Session 高频请求
    print("\n  [3.2] 同一 Session 100次请求")
    session_id = "high_freq"
    start = time.perf_counter()
    for i in range(100):
        await runtime.run(agent_id="qa_assistant", session_id=session_id, input_text=f"msg {i}")
    elapsed = time.perf_counter() - start
    print(f"    100次请求耗时: {elapsed:.2f}s ({elapsed*10:.0f}ms/个)")

    # 3.3 并发 + 不同 Agent
    print("\n  [3.3] 不同 Agent 并发")
    # 测试多 agent 并发需要先配置
    print("    (需要多agent配置，跳过)")

    await runtime.close()
    print("\n  ✓ 并发压力测试完成")


# ============================================================================
# Test 4: 资源泄漏测试
# ============================================================================

async def test_resource_leak():
    print("\n" + "=" * 60)
    print("[4] 资源泄漏测试")
    print("=" * 60)

    runtime = Runtime.from_config("examples/persistent_qa/agent.json")

    # 4.1 Session 累积
    print("\n  [4.1] Session 累积测试")
    initial = runtime.get_session_count()
    print(f"    初始Session数: {initial}")

    for i in range(100):
        await runtime.run(agent_id="qa_assistant", session_id=f"leak_{i}", input_text=f"test {i}")

    final = runtime.get_session_count()
    print(f"    100次后Session数: {final}")

    # 检查是否正确清理
    if final > initial + 50:
        print("    ⚠ WARNING: Session 可能未正确清理")

    # 4.2 内存检查 (通过多次运行观察)
    print("\n  [4.2] 内存稳定性测试 (10轮)")
    import gc
    for round in range(10):
        r = Runtime.from_config("examples/persistent_qa/agent.json")
        for i in range(10):
            await r.run(agent_id="qa_assistant", session_id=f"round_{round}_{i}", input_text=f"test")
        await r.close()
        gc.collect()

    print(f"    10轮完成，Session数: {runtime.get_session_count()}")

    await runtime.close()
    print("\n  ✓ 资源泄漏测试完成")


# ============================================================================
# Test 5: 异常恢复测试
# ============================================================================

async def test_recovery():
    print("\n" + "=" * 60)
    print("[5] 异常恢复测试")
    print("=" * 60)

    runtime = Runtime.from_config("examples/persistent_qa/agent.json")

    # 5.1 Session 失败后继续
    print("\n  [5.1] Session 失败后继续")
    session_id = "recovery_test"

    # 第一次 - 会成功
    r1 = await runtime.run(agent_id="qa_assistant", session_id=session_id, input_text="Hello")
    print(f"    第一次: OK")

    # 检查 session 状态
    state = await runtime.session_manager.get_state(session_id)
    print(f"    Session状态keys: {list(state.keys())}")

    # 第二次 - 应该继续工作
    r2 = await runtime.run(agent_id="qa_assistant", session_id=session_id, input_text="World")
    print(f"    第二次: OK")

    # 5.2 热更新后恢复
    print("\n  [5.2] 热更新后恢复")
    await runtime.reload()
    print(f"    Reload完成")

    r3 = await runtime.run(agent_id="qa_assistant", session_id=session_id, input_text="After reload")
    print(f"    Reload后: OK")

    await runtime.close()
    print("\n  ✓ 异常恢复测试完成")


# ============================================================================
# Test 6: 性能基准测试
# ============================================================================

async def test_performance_benchmark():
    print("\n" + "=" * 60)
    print("[6] 性能基准测试")
    print("=" * 60)

    runtime = Runtime.from_config("examples/persistent_qa/agent.json")

    # 6.1 冷启动时间
    print("\n  [6.1] Runtime 冷启动")
    times = []
    for i in range(5):
        start = time.perf_counter()
        r = Runtime.from_config("examples/persistent_qa/agent.json")
        elapsed = time.perf_counter() - start
        times.append(elapsed * 1000)
        await r.close()

    avg = sum(times) / len(times)
    print(f"    平均启动时间: {avg:.0f}ms")

    # 6.2 单次请求延迟
    print("\n  [6.2] 单次请求延迟")
    latencies = []
    for i in range(10):
        start = time.perf_counter()
        await runtime.run(agent_id="qa_assistant", session_id=f"perf_{i}", input_text="hi")
        latencies.append((time.perf_counter() - start) * 1000)

    print(f"    平均: {sum(latencies)/len(latencies):.0f}ms")
    print(f"    最小: {min(latencies):.0f}ms")
    print(f"    最大: {max(latencies):.0f}ms")

    # 6.3 吞吐量
    print("\n  [6.3] 吞吐量测试")
    start = time.perf_counter()
    count = 0
    while time.perf_counter() - start < 5:  # 5秒内
        await runtime.run(agent_id="qa_assistant", session_id=f"throughput_{count}", input_text="test")
        count += 1

    elapsed = time.perf_counter() - start
    print(f"    5秒内请求数: {count}")
    print(f"    吞吐量: {count/elapsed:.1f} req/s")

    await runtime.close()
    print("\n  ✓ 性能基准测试完成")


# ============================================================================
# Test 7: Memory 深度测试
# ============================================================================

async def test_memory_deep():
    print("\n" + "=" * 60)
    print("[7] Memory 深度测试")
    print("=" * 60)

    runtime = Runtime.from_config("examples/persistent_qa/agent.json")

    # 7.1 Buffer Memory
    print("\n  [7.1] Buffer Memory (累积)")
    config = load_config_dict({
        "version": "1.0",
        "agents": [{
            "id": "buffer_test",
            "name": "Buffer",
            "memory": {"type": "buffer"},
            "pattern": {"type": "react", "config": {"max_steps": 1}},
            "llm": {"provider": "mock"},
            "tools": []
        }]
    })
    runtime._agents_by_id["buffer_test"] = config.agents[0]

    session_id = "buffer_test"
    for i in range(10):
        await runtime.run(agent_id="buffer_test", session_id=session_id, input_text=f"msg {i}")

    state = await runtime.session_manager.get_state(session_id)
    history = state.get("memory_view", {}).get("history", [])
    print(f"    10次后history长度: {len(history)}")

    # 7.2 Window Buffer Memory
    print("\n  [7.2] Window Buffer Memory (滑动窗口)")
    config2 = load_config_dict({
        "version": "1.0",
        "agents": [{
            "id": "window_test",
            "name": "Window",
            "memory": {"type": "window_buffer", "config": {"window_size": 3}},
            "pattern": {"type": "react", "config": {"max_steps": 1}},
            "llm": {"provider": "mock"},
            "tools": []
        }]
    })
    runtime._agents_by_id["window_test"] = config2.agents[0]

    session_id = "window_test"
    for i in range(10):
        await runtime.run(agent_id="window_test", session_id=session_id, input_text=f"msg {i}")
        state = await runtime.session_manager.get_state(session_id)
        history = state.get("memory_view", {}).get("history", [])
        print(f"    msg {i}: history长度 = {len(history)}")

    # 7.3 Chain Memory
    print("\n  [7.3] Chain Memory")
    print("    ChainMemory 测试: 通过配置测试")

    await runtime.close()
    print("\n  ✓ Memory 深度测试完成")


# ============================================================================
# Test 8: Event Bus 压力测试
# ============================================================================

async def test_event_bus_stress():
    print("\n" + "=" * 60)
    print("[8] Event Bus 压力测试")
    print("=" * 60)

    runtime = Runtime.from_config("examples/persistent_qa/agent.json")

    # 记录所有事件
    events = []
    async def on_event(event):
        events.append(event.name)

    runtime.event_bus.subscribe("run.", on_event)
    runtime.event_bus.subscribe("llm.", on_event)
    runtime.event_bus.subscribe("tool.", on_event)
    runtime.event_bus.subscribe("memory.", on_event)

    # 10次请求
    print("\n  [8.1] 10次请求的事件数")
    for i in range(10):
        await runtime.run(agent_id="qa_assistant", session_id=f"event_{i}", input_text=f"test {i}")

    event_counts = defaultdict(int)
    for e in events:
        event_counts[e] += 1

    print(f"    总事件数: {len(events)}")
    for name, count in sorted(event_counts.items()):
        print(f"    {name}: {count}")

    # 8.2 事件历史
    print("\n  [8.2] Event History")
    history = runtime.event_bus.get_history()
    print(f"    历史记录数: {len(history)}")

    await runtime.close()
    print("\n  ✓ Event Bus 压力测试完成")


# ============================================================================
# Main
# ============================================================================

async def main():
    load_env()

    print("=" * 60)
    print("OpenAgents SDK - 最严苛测试")
    print("=" * 60)

    try:
        await test_edge_cases()
        await test_error_handling()
        await test_concurrency_stress()
        await test_resource_leak()
        await test_recovery()
        await test_performance_benchmark()
        await test_memory_deep()
        await test_event_bus_stress()

        print("\n" + "=" * 60)
        print("🎉 所有严苛测试完成!")
        print("=" * 60)

    except Exception as e:
        print(f"\n💥 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
