"""ProviderPool P0 修复回归测试 (Issue #7).

覆盖: 信号量迭代期持有、流式异常计数、调用点只读拒绝 (Q-H1)、
半开单飞探测 (Q-L1)、健康检查缓存、手动重置熔断器等。
"""
import asyncio
import inspect
import time
from unittest.mock import MagicMock

import pytest

CFG = {"llm_provider": "openai", "model_name": "gpt-4o"}
KEY = "openai:gpt-4o"


class FakeLLMProvider:
    """可编程 fake provider: get_response_stream 返回可配置的 async generator."""

    def __init__(self) -> None:
        self.stream_factory = None
        self.health_result = {
            "healthy": True,
            "latency_ms": 1.0,
            "model": "fake",
            "error": None,
        }
        self.health_error = None
        self.health_calls = 0

    def get_response_stream(self, messages, images=None, tools=None, tool_functions=None):
        """返回可编程 async generator（默认 yield ("final", "ok")）."""
        if self.stream_factory is None:

            async def _default():
                yield "final", "ok"

            return _default()
        return self.stream_factory(messages, images, tools, tool_functions)

    async def check_health(self):
        """记录调用次数并返回健康结果（或抛出配置的错误）."""
        self.health_calls += 1
        if self.health_error is not None:
            raise self.health_error
        return dict(self.health_result)


async def _stream(*items):
    """yield 固定序列的 async generator."""
    for item in items:
        yield item


async def _raise_stream(exc):
    """立即抛出异常的 async generator."""
    raise exc
    yield  # pragma: no cover


async def _consume(generator):
    """完整消费 async generator 并收集产出."""
    collected = []
    async for item in generator:
        collected.append(item)
    return collected


@pytest.fixture
def fake_provider() -> FakeLLMProvider:
    return FakeLLMProvider()


@pytest.fixture
def make_pool(monkeypatch, fake_provider):
    """工厂 fixture: 每次调用创建独立 ProviderPool（避免跨 loop 绑定）."""

    def _make(**kwargs):
        from app.llm_providers.provider_pool import ProviderPool

        mock_get = MagicMock(return_value=fake_provider)
        monkeypatch.setattr(
            "app.llm_providers.provider_pool.get_llm_provider", mock_get
        )
        return ProviderPool(**kwargs)

    return _make


@pytest.fixture
def pool(make_pool):
    """默认参数 ProviderPool（function-scope）."""
    return make_pool()


def _open_backdated_breaker(pool) -> dict:
    """手工打开熔断器并将 last_failure 置于重置窗口之外."""
    pool._circuit_breakers[KEY] = pool._new_circuit_breaker()
    cb = pool._circuit_breakers[KEY]
    cb["open"] = True
    cb["failure_count"] = 1
    cb["last_failure"] = time.monotonic() - 1000
    return cb


class TestExecute:
    async def test_execute_returns_wrapped_async_generator(self, pool):
        gen = await pool.execute(CFG, [{"role": "user", "content": "hi"}])
        assert inspect.isasyncgen(gen)
        assert await _consume(gen) == [("final", "ok")]

    async def test_semaphore_held_through_entire_consumption(
        self, make_pool, fake_provider
    ):
        # P0 回归: 信号量必须在迭代期间持有（旧实现仅覆盖 execute() 调用点）
        pool = make_pool(max_concurrent_per_provider=1)
        entered = asyncio.Event()
        release = asyncio.Event()
        state = {"current": 0, "max_seen": 0}

        async def gated_stream(*_args):
            state["current"] += 1
            state["max_seen"] = max(state["max_seen"], state["current"])
            try:
                entered.set()
                await release.wait()
                yield "final", "ok"
            finally:
                state["current"] -= 1

        fake_provider.stream_factory = gated_stream

        gen_a = await pool.execute(CFG, [{"role": "user", "content": "a"}])
        gen_b = await pool.execute(CFG, [{"role": "user", "content": "b"}])

        task_a = asyncio.create_task(_consume(gen_a))
        task_b = asyncio.create_task(_consume(gen_b))

        await entered.wait()  # A 已进入流（持有信号量）
        assert state["max_seen"] == 1  # B 必须阻塞在信号量上

        release.set()
        results = await asyncio.gather(task_a, task_b)
        assert results == [[("final", "ok")], [("final", "ok")]]

        stats = pool.get_stats()
        assert stats[KEY]["requests"] == 2
        assert stats[KEY]["errors"] == 0

    async def test_stream_exception_counts_error_and_opens_breaker(
        self, make_pool, fake_provider
    ):
        # P0 回归: 流式迭代异常必须计数并触发熔断（旧实现仅在创建时计数）
        pool = make_pool(circuit_breaker_threshold=2)
        fake_provider.stream_factory = lambda *a: _raise_stream(RuntimeError("boom"))

        for _ in range(2):
            gen = await pool.execute(CFG, [{"role": "user", "content": "hi"}])
            with pytest.raises(RuntimeError, match="boom"):
                await _consume(gen)

        stats = pool.get_stats()
        assert stats[KEY]["errors"] == 2
        assert stats[KEY]["requests"] == 2
        cb = pool._circuit_breakers[KEY]
        assert cb["open"] is True

        with pytest.raises(RuntimeError, match="Circuit breaker open"):
            await pool.execute(CFG, [{"role": "user", "content": "hi"}])

    async def test_breaker_half_open_recovers_after_reset_window(
        self, make_pool, fake_provider
    ):
        pool = make_pool(circuit_breaker_threshold=1)
        fake_provider.stream_factory = lambda *a: _raise_stream(RuntimeError("boom"))

        gen = await pool.execute(CFG, [{"role": "user", "content": "hi"}])
        with pytest.raises(RuntimeError, match="boom"):
            await _consume(gen)
        assert pool._circuit_breakers[KEY]["open"] is True

        pool._circuit_breakers[KEY]["last_failure"] = time.monotonic() - 1000

        fake_provider.stream_factory = None  # 恢复成功流
        gen2 = await pool.execute(CFG, [{"role": "user", "content": "hi"}])
        assert await _consume(gen2) == [("final", "ok")]

        cb = pool._circuit_breakers[KEY]
        assert cb["open"] is False
        assert cb["failure_count"] == 0
        assert cb["probe_in_flight"] is False

    async def test_half_open_allows_single_probe_concurrently(
        self, make_pool, fake_provider
    ):
        pool = make_pool(circuit_breaker_threshold=1)
        _open_backdated_breaker(pool)

        started = asyncio.Event()
        release = asyncio.Event()

        async def gated_stream(*_args):
            started.set()
            await release.wait()
            yield "final", "ok"

        fake_provider.stream_factory = gated_stream

        gen_probe = await pool.execute(CFG, [{"role": "user", "content": "probe"}])
        task = asyncio.create_task(_consume(gen_probe))
        await started.wait()  # 探测已进入流（probe_in_flight=True）

        with pytest.raises(RuntimeError, match="half-open, probe in flight"):
            gen2 = await pool.execute(CFG, [{"role": "user", "content": "second"}])
            await _consume(gen2)

        release.set()
        assert await task == [("final", "ok")]

    async def test_early_break_still_recovers_breaker(
        self, make_pool, fake_provider
    ):
        # MEDIUM-2 回归: 探测成功但消费方 break 提前终止 → 熔断器收敛
        # （生产路径: bot_instance._get_llm_response 收到 "final" 即 break 并显式 aclose）
        pool = make_pool(circuit_breaker_threshold=1)
        _open_backdated_breaker(pool)

        fake_provider.stream_factory = lambda *a: _stream(
            ("partial", "hello"), ("final", "ok")
        )
        gen = await pool.execute(CFG, [{"role": "user", "content": "hi"}])
        collected = []
        async for item in gen:
            collected.append(item)
            if item[0] == "final":
                await gen.aclose()  # 与 bot_instance 一致: break 前显式关闭
                break

        assert collected == [("partial", "hello"), ("final", "ok")]
        cb = pool._circuit_breakers[KEY]
        assert cb["open"] is False  # 无异常 → 收敛重置
        assert cb["failure_count"] == 0
        assert cb["probe_in_flight"] is False
        assert pool.get_stats()[KEY]["errors"] == 0

    async def test_close_from_cancelled_other_task_still_recovers(
        self, make_pool, fake_provider
    ):
        # MEDIUM-2: 事件循环 finalizer 路径 —— 3.12+ 的 _asyncgen_finalizer_hook 以
        # create_task(aclose) 方式关闭被抛弃的生成器，shutdown 时该任务被取消，
        # CancelledError 从非消费方任务投递 → 流无失败证据 → 熔断器收敛。
        # （真实用户取消仍不收敛，见 TestCancellation.test_cancel_...）
        pool = make_pool(circuit_breaker_threshold=1)
        _open_backdated_breaker(pool)
        fake_provider.stream_factory = lambda *a: _stream(
            ("partial", "hello"), ("final", "ok")
        )
        gen = await pool.execute(CFG, [{"role": "user", "content": "hi"}])
        async for resp_type, data in gen:
            if resp_type == "final":
                break  # 不显式关闭 → 依赖 finalizer 兜底

        closer = asyncio.create_task(gen.aclose())
        closer.cancel()  # 模拟 shutdown 时 finalizer 任务被取消
        with pytest.raises(asyncio.CancelledError):
            await closer

        cb = pool._circuit_breakers[KEY]
        assert cb["open"] is False
        assert cb["failure_count"] == 0
        assert cb["probe_in_flight"] is False
        assert pool.get_stats()[KEY]["errors"] == 0

    async def test_error_marker_final_counts_and_opens_breaker(
        self, make_pool, fake_provider
    ):
        # MEDIUM-3 回归: provider 层吞异常为 "final" + LLM_PROVIDER_ERROR 前缀 →
        # pool 计数 errors 并触发熔断，且不打断输出契约
        pool = make_pool(circuit_breaker_threshold=1)
        fake_provider.stream_factory = lambda *a: _stream(
            ("final", "LLM_PROVIDER_ERROR: OpenAIProvider encountered an error: boom")
        )

        gen = await pool.execute(CFG, [{"role": "user", "content": "hi"}])
        # 调用方仍收到 final 错误标记（契约不变）
        assert await _consume(gen) == [
            ("final", "LLM_PROVIDER_ERROR: OpenAIProvider encountered an error: boom")
        ]

        stats = pool.get_stats()
        assert stats[KEY]["errors"] == 1
        assert stats[KEY]["requests"] == 1
        cb = pool._circuit_breakers[KEY]
        assert cb["open"] is True
        assert cb["failure_count"] == 1

        # 熔断打开 → 调用点只读拒绝
        with pytest.raises(RuntimeError, match="Circuit breaker open"):
            await pool.execute(CFG, [{"role": "user", "content": "hi"}])


class TestCollectFullResponse:
    async def test_collect_full_response_success(self, pool, fake_provider):
        fake_provider.stream_factory = lambda *a: _stream(
            ("partial", "a"), ("final", "done"), ("usage", {"total_tokens": 10})
        )
        full, usage = await pool.collect_full_response(
            CFG, [{"role": "user", "content": "hi"}]
        )
        assert full == "done"
        assert usage == {"total_tokens": 10}

    async def test_collect_full_response_propagates_stream_error(
        self, make_pool, fake_provider
    ):
        # P0 回归: collect_full_response 消费期间的异常必须计数并熔断
        pool = make_pool(circuit_breaker_threshold=1)
        fake_provider.stream_factory = lambda *a: _raise_stream(
            RuntimeError("stream failed")
        )
        with pytest.raises(RuntimeError, match="stream failed"):
            await pool.collect_full_response(CFG, [{"role": "user", "content": "hi"}])
        assert pool.get_stats()[KEY]["errors"] == 1
        assert pool._circuit_breakers[KEY]["open"] is True


class TestCancellation:
    async def test_cancel_during_stream_not_counted_and_releases_semaphore(
        self, pool, fake_provider
    ):
        started = asyncio.Event()
        release = asyncio.Event()

        async def gated_stream(*_args):
            started.set()
            await release.wait()
            yield "final", "ok"

        fake_provider.stream_factory = gated_stream

        gen = await pool.execute(CFG, [{"role": "user", "content": "hi"}])
        task = asyncio.create_task(_consume(gen))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        stats = pool.get_stats()
        assert stats[KEY]["errors"] == 0  # 取消不计数

        # 信号量已释放: 后续请求可正常消费
        fake_provider.stream_factory = None
        gen2 = await pool.execute(CFG, [{"role": "user", "content": "hi"}])
        assert await _consume(gen2) == [("final", "ok")]


class TestCircuitBreaker:
    async def test_execute_fail_fast_when_breaker_open(self, pool):
        cb = pool._circuit_breakers[KEY] = pool._new_circuit_breaker()
        cb["open"] = True
        cb["failure_count"] = 3
        cb["last_failure"] = time.monotonic()  # 窗口未过期

        with pytest.raises(RuntimeError, match="Circuit breaker open"):
            await pool.execute(CFG, [{"role": "user", "content": "hi"}])

        # Q-H1: 调用点拒绝零副作用
        assert pool.get_stats() == {}
        assert pool._circuit_breakers[KEY]["open"] is True
        assert pool._circuit_breakers[KEY]["failure_count"] == 3

    async def test_reset_circuit_breaker_manual(self, make_pool, fake_provider):
        pool = make_pool(circuit_breaker_threshold=1)
        fake_provider.stream_factory = lambda *a: _raise_stream(RuntimeError("boom"))

        gen = await pool.execute(CFG, [{"role": "user", "content": "hi"}])
        with pytest.raises(RuntimeError, match="boom"):
            await _consume(gen)
        assert pool._circuit_breakers[KEY]["open"] is True

        pool.reset_circuit_breaker(KEY)
        cb = pool._circuit_breakers[KEY]
        assert cb["open"] is False
        assert cb["failure_count"] == 0
        assert cb["probe_in_flight"] is False

        fake_provider.stream_factory = None
        gen2 = await pool.execute(CFG, [{"role": "user", "content": "hi"}])
        assert await _consume(gen2) == [("final", "ok")]

    async def test_window_expired_first_execute_does_not_reset(self, pool):
        # Q-H1 回归: 窗口过期后 execute 放行创建 generator，但调用点不重置/不计数
        _open_backdated_breaker(pool)

        gen = await pool.execute(CFG, [{"role": "user", "content": "hi"}])
        assert inspect.isasyncgen(gen)

        cb = pool._circuit_breakers[KEY]
        assert cb["open"] is True  # 未被调用点重置
        assert cb["failure_count"] == 1  # 不归零
        assert pool.get_stats() == {}  # 未计数

    async def test_half_open_probe_rejection_not_counted(
        self, make_pool, fake_provider
    ):
        # Q-L1 回归: 探测在途时的拒绝不计 errors、不更新 last_failure
        pool = make_pool(circuit_breaker_threshold=1)
        cb = _open_backdated_breaker(pool)
        before_last_failure = cb["last_failure"]

        started = asyncio.Event()
        release = asyncio.Event()

        async def gated_stream(*_args):
            started.set()
            await release.wait()
            yield "final", "ok"

        fake_provider.stream_factory = gated_stream

        gen_probe = await pool.execute(CFG, [{"role": "user", "content": "probe"}])
        task = asyncio.create_task(_consume(gen_probe))
        await started.wait()  # 探测在途

        gen2 = await pool.execute(CFG, [{"role": "user", "content": "second"}])
        with pytest.raises(RuntimeError, match="half-open, probe in flight"):
            await _consume(gen2)

        stats = pool.get_stats()
        assert stats[KEY]["errors"] == 0
        cb = pool._circuit_breakers[KEY]
        assert cb["failure_count"] == 1  # 不变
        assert cb["last_failure"] == before_last_failure  # 不更新

        release.set()
        await task


class TestHealthCheck:
    async def test_check_provider_health_cache_and_force(self, pool, fake_provider):
        h1 = await pool.check_provider_health(CFG)
        assert h1["healthy"] is True
        assert fake_provider.health_calls == 1

        h2 = await pool.check_provider_health(CFG)
        assert fake_provider.health_calls == 1  # 缓存命中
        assert h2 == h1

        h3 = await pool.check_provider_health(CFG, force=True)
        assert fake_provider.health_calls == 2
        assert h3 == h1

    async def test_health_check_error_captured(self, pool, fake_provider):
        fake_provider.health_error = RuntimeError("provider down")
        health = await pool.check_provider_health(CFG)
        assert health == {"healthy": False, "error": "provider down"}


class TestStats:
    async def test_get_stats_shape(self, pool):
        gen = await pool.execute(CFG, [{"role": "user", "content": "hi"}])
        await _consume(gen)
        stats = pool.get_stats()
        assert stats[KEY] == {
            "requests": 1,
            "errors": 0,
            "input_tokens": 0,
            "output_tokens": 0,
        }
        # get_stats 返回副本
        stats[KEY]["requests"] = 99
        assert pool.get_stats()[KEY]["requests"] == 1

    async def test_unsupported_provider_raises_not_counted(
        self, monkeypatch, make_pool
    ):
        pool = make_pool()
        monkeypatch.setattr(
            "app.llm_providers.provider_pool.get_llm_provider",
            MagicMock(side_effect=ValueError("Unsupported LLM provider: 'nope'")),
        )
        with pytest.raises(ValueError, match="Unsupported"):
            await pool.execute(
                {"llm_provider": "nope"}, [{"role": "user", "content": "hi"}]
            )
        assert pool.get_stats() == {}
