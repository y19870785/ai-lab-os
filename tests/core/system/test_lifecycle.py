"""System lifecycle tests — monkeypatch real components, no test hooks."""

import asyncio
from pathlib import Path
import tempfile

import pytest

from core.system.lifecycle import SystemLifecycleState
from core.system.settings import make_test_settings
from core.system.factory import create_system
from core.system.exceptions import SystemInitializationError
from core.errors import ErrorCategory, FailureException


class BlockingCloser:
    def __init__(self):
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.close_count = 0

    async def __call__(self):
        self.close_count += 1
        self.started.set()
        await self.release.wait()


def _make_system():
    data_dir = Path(tempfile.mkdtemp(prefix="ai-lab-sp007-"))
    settings = make_test_settings(data_dir, enable_knowledge=False)
    loop = asyncio.new_event_loop()
    return loop.run_until_complete(create_system(settings)), loop


class TestConcurrentShutdown:
    def test_concurrent_shutdown_all_wait_close_count_once(self):
        system, loop = _make_system()
        loop.run_until_complete(system.start())
        assert system.lifecycle_state == SystemLifecycleState.READY

        blocker = BlockingCloser()
        system.database_manager.close_all = blocker

        async def _run():
            first = asyncio.create_task(system.shutdown())
            await blocker.started.wait()
            second = asyncio.create_task(system.shutdown())
            third = asyncio.create_task(system.shutdown())
            await asyncio.sleep(0)
            assert not first.done()
            assert not second.done()
            assert not third.done()
            blocker.release.set()
            await asyncio.gather(first, second, third)
            assert blocker.close_count == 1
            assert system.lifecycle_state == SystemLifecycleState.STOPPED
        loop.run_until_complete(_run())

    def test_cleanup_failure_reaches_failed(self):
        system, loop = _make_system()
        loop.run_until_complete(system.start())

        async def failing_close():
            raise RuntimeError("injected failure")
        system.database_manager.close_all = failing_close

        loop.run_until_complete(system.shutdown())
        assert system.lifecycle_state == SystemLifecycleState.FAILED
        assert not system.accepting_work
        assert "database_manager" in system.shutdown_failures


class TestDrainingGate:
    def test_draining_gate_during_active_shutdown(self):
        system, loop = _make_system()
        loop.run_until_complete(system.start())

        blocker = BlockingCloser()
        system.database_manager.close_all = blocker

        async def _run():
            shutdown_task = asyncio.create_task(system.shutdown())
            await blocker.started.wait()
            assert system.lifecycle_state == SystemLifecycleState.DRAINING
            with pytest.raises(FailureException) as e:
                system.ensure_accepting_work()
            assert e.value.failure.code == "system.draining"
            assert e.value.failure.category == ErrorCategory.UNAVAILABLE
            assert e.value.failure.component == "system.lifecycle"
            assert e.value.failure.operation == "admit_request"
            assert e.value.failure.retryable is True
            blocker.release.set()
            await shutdown_task
        loop.run_until_complete(_run())


class TestStartRejection:
    def test_start_rejected_while_starting(self):
        system, loop = _make_system()
        loop.run_until_complete(system._lifecycle.transition(SystemLifecycleState.STARTING))
        with pytest.raises(SystemInitializationError, match="in progress"):
            loop.run_until_complete(system.start())

    def test_start_rejected_while_draining(self):
        system, loop = _make_system()
        loop.run_until_complete(system.start())
        loop.run_until_complete(system._lifecycle.transition(SystemLifecycleState.DRAINING))
        with pytest.raises(SystemInitializationError, match="draining"):
            loop.run_until_complete(system.start())


class TestAllAdmissionCodes:
    def _assert_failure(self, exc_info, code):
        f = exc_info.value.failure
        assert f.code == code, f"expected {code}, got {f.code}"
        assert f.category == ErrorCategory.UNAVAILABLE
        assert f.component == "system.lifecycle"
        assert f.operation == "admit_request"
        assert f.retryable is True

    def test_all_admission_codes(self):
        system, loop = _make_system()

        # CREATED -> system.not_ready
        with pytest.raises(FailureException) as e:
            system.ensure_accepting_work()
        self._assert_failure(e, "system.not_ready")

        # STARTING -> system.not_ready
        loop.run_until_complete(system._lifecycle.transition(SystemLifecycleState.STARTING))
        with pytest.raises(FailureException) as e:
            system.ensure_accepting_work()
        self._assert_failure(e, "system.not_ready")

        # READY -> no exception
        loop.run_until_complete(system._lifecycle.transition(SystemLifecycleState.READY))
        system.ensure_accepting_work()

        # DRAINING -> system.draining
        loop.run_until_complete(system._lifecycle.transition(SystemLifecycleState.DRAINING))
        with pytest.raises(FailureException) as e:
            system.ensure_accepting_work()
        self._assert_failure(e, "system.draining")

        # STOPPED -> system.stopped
        loop.run_until_complete(system._lifecycle.transition(SystemLifecycleState.STOPPED))
        with pytest.raises(FailureException) as e:
            system.ensure_accepting_work()
        self._assert_failure(e, "system.stopped")

        # FAILED -> system.failed
        system2, loop2 = _make_system()
        loop2.run_until_complete(system2._lifecycle.transition(SystemLifecycleState.STARTING))
        loop2.run_until_complete(system2._lifecycle.transition(SystemLifecycleState.FAILED))
        with pytest.raises(FailureException) as e:
            system2.ensure_accepting_work()
        self._assert_failure(e, "system.failed")


class TestHealthExactStates:
    def test_health_created(self):
        system, loop = _make_system()
        health = loop.run_until_complete(system.health())
        assert health["lifecycle"] == "created"
        assert health["accepting_work"] is False

    def test_health_starting(self):
        system, loop = _make_system()
        loop.run_until_complete(system._lifecycle.transition(SystemLifecycleState.STARTING))
        health = loop.run_until_complete(system.health())
        assert health["lifecycle"] == "starting"
        assert health["accepting_work"] is False

    def test_health_ready(self):
        system, loop = _make_system()
        loop.run_until_complete(system.start())
        health = loop.run_until_complete(system.health())
        assert health["lifecycle"] == "ready"
        assert health["accepting_work"] is True
        loop.run_until_complete(system.shutdown())


@pytest.mark.asyncio
async def test_waiting_for_and_agenda_exist_when_reminders_and_scheduler_are_disabled(
    tmp_path,
):
    settings = make_test_settings(
        tmp_path,
        enable_reminders=False,
        enable_scheduler=False,
    )
    system = await create_system(settings)
    await system.start()
    try:
        assert system.waiting_for_service is not None
        assert system.daily_agenda is not None
        health = await system.health()
        assert health["components"]["waiting_for"]["status"] == "healthy"
    finally:
        await system.shutdown()
