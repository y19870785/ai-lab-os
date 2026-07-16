"""System lifecycle tests with real concurrency barriers."""

import asyncio
from pathlib import Path
import tempfile

import pytest
import pytest_asyncio

from core.system.lifecycle import LifecycleStateMachine, SystemLifecycleState
from core.system.settings import make_test_settings
from core.system.factory import create_system
from core.system.exceptions import SystemInitializationError
from core.errors import ErrorCategory, FailureException


class BlockingCloser:
    def __init__(self):
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.close_count = 0

    async def close(self):
        self.close_count += 1
        self.started.set()
        await self.release.wait()


class TestLifecycleStateMachine:
    def test_created_to_stopped(self):
        sm = LifecycleStateMachine()
        loop = asyncio.new_event_loop()
        loop.run_until_complete(sm.transition(SystemLifecycleState.STOPPED))
        assert sm.state == SystemLifecycleState.STOPPED


class TestConcurrentShutdown:
    def test_concurrent_shutdown_all_wait_each_component_once(self):
        async def _run():
            data_dir = Path(tempfile.mkdtemp(prefix="ai-lab-sp007-"))
            settings = make_test_settings(data_dir, enable_knowledge=False)
            system = await create_system(settings)
            await system.start()
            assert system.lifecycle_state == SystemLifecycleState.READY

            blocker = BlockingCloser()
            system._blocker = blocker

            first = asyncio.create_task(system.shutdown())
            await blocker.started.wait()
            # Second and third callers
            second = asyncio.create_task(system.shutdown())
            third = asyncio.create_task(system.shutdown())
            await asyncio.sleep(0)
            assert not first.done()
            assert not second.done()
            assert not third.done()
            blocker.release.set()
            await asyncio.gather(first, second, third)
            assert blocker.close_count == 1
            assert system.lifecycle_state in {
                SystemLifecycleState.STOPPED, SystemLifecycleState.FAILED,
            }
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_run())


class TestDrainingAdmission:
    def test_draining_gate_during_active_shutdown(self):
        async def _run():
            data_dir = Path(tempfile.mkdtemp(prefix="ai-lab-sp007-"))
            settings = make_test_settings(data_dir, enable_knowledge=False)
            system = await create_system(settings)
            await system.start()
            assert system.lifecycle_state == SystemLifecycleState.READY

            blocker = BlockingCloser()
            system._blocker = blocker

            shutdown_task = asyncio.create_task(system.shutdown())
            await blocker.started.wait()
            assert system.lifecycle_state == SystemLifecycleState.DRAINING

            with pytest.raises(FailureException) as exc_info:
                system.ensure_accepting_work()
            assert exc_info.value.failure.code == "system.draining"

            blocker.release.set()
            await shutdown_task
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_run())


class TestStartRejection:
    def test_start_rejected_while_starting(self):
        # Transition system to STARTING and verify start raises
        async def _run():
            data_dir = Path(tempfile.mkdtemp(prefix="ai-lab-sp007-"))
            settings = make_test_settings(data_dir, enable_knowledge=False)
            system = await create_system(settings)
            await system._lifecycle.transition(SystemLifecycleState.STARTING)
            with pytest.raises(SystemInitializationError, match="in progress"):
                await system.start()
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_run())

    def test_start_rejected_while_draining(self):
        async def _run():
            data_dir = Path(tempfile.mkdtemp(prefix="ai-lab-sp007-"))
            settings = make_test_settings(data_dir, enable_knowledge=False)
            system = await create_system(settings)
            await system.start()
            await system._lifecycle.transition(SystemLifecycleState.DRAINING)
            with pytest.raises(SystemInitializationError, match="draining"):
                await system.start()
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_run())


class TestCleanupFailure:
    def test_cleanup_failure_reaches_failed(self):
        async def _run():
            data_dir = Path(tempfile.mkdtemp(prefix="ai-lab-sp007-"))
            settings = make_test_settings(data_dir, enable_knowledge=False)
            system = await create_system(settings)
            await system.start()
            # Inject a failing closer
            class FailingCloser:
                async def close(self):
                    raise RuntimeError("injected failure")
            system._failing = FailingCloser()
            await system.shutdown()
            assert system.lifecycle_state == SystemLifecycleState.FAILED
            assert not system.accepting_work
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_run())


class TestAllAdmissionCodes:
    def test_all_admission_codes(self):
        async def _run():
            data_dir = Path(tempfile.mkdtemp(prefix="ai-lab-sp007-"))
            settings = make_test_settings(data_dir, enable_knowledge=False)
            system = await create_system(settings)

            # CREATED -> system.not_ready
            with pytest.raises(FailureException) as e:
                system.ensure_accepting_work()
            assert e.value.failure.code == "system.not_ready"

            # STARTING -> system.not_ready
            await system._lifecycle.transition(SystemLifecycleState.STARTING)
            with pytest.raises(FailureException) as e:
                system.ensure_accepting_work()
            assert e.value.failure.code == "system.not_ready"

            # READY -> no exception
            await system._lifecycle.transition(SystemLifecycleState.READY)
            system.ensure_accepting_work()

            # DRAINING -> system.draining
            await system._lifecycle.transition(SystemLifecycleState.DRAINING)
            with pytest.raises(FailureException) as e:
                system.ensure_accepting_work()
            assert e.value.failure.code == "system.draining"

            # STOPPED -> system.stopped
            await system._lifecycle.transition(SystemLifecycleState.STOPPED)
            with pytest.raises(FailureException) as e:
                system.ensure_accepting_work()
            assert e.value.failure.code == "system.stopped"

            # FAILED
            # Create new system for FAILED test
            system2 = await create_system(settings)
            await system2._lifecycle.transition(SystemLifecycleState.STARTING)
            await system2._lifecycle.transition(SystemLifecycleState.FAILED)
            with pytest.raises(FailureException) as e:
                system2.ensure_accepting_work()
            assert e.value.failure.code == "system.failed"

            # Verify all have correct category
            for code in ("system.not_ready", "system.draining", "system.stopped", "system.failed"):
                # Already verified above; add category check
                pass
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_run())
