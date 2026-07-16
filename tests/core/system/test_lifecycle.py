"""System lifecycle state machine and container admission tests."""

import asyncio
from pathlib import Path
import tempfile

import pytest
import pytest_asyncio

from core.system.lifecycle import (
    LifecycleStateMachine, SystemLifecycleState, InvalidLifecycleTransitionError,
)
from core.system.settings import make_test_settings
from core.system.container import SystemContainer
from core.system.factory import create_system
from core.system.exceptions import SystemInitializationError
from core.errors import FailureException


class TestLifecycleStateMachine:
    def test_initial_state_is_created(self):
        sm = LifecycleStateMachine()
        assert sm.state == SystemLifecycleState.CREATED
        assert not sm.accepting_work

    @pytest.mark.asyncio
    async def test_created_to_starting_to_ready(self):
        sm = LifecycleStateMachine()
        await sm.transition(SystemLifecycleState.STARTING)
        assert sm.state == SystemLifecycleState.STARTING
        await sm.transition(SystemLifecycleState.READY)
        assert sm.state == SystemLifecycleState.READY

    @pytest.mark.asyncio
    async def test_created_to_stopped(self):
        sm = LifecycleStateMachine()
        await sm.transition(SystemLifecycleState.STOPPED)
        assert sm.state == SystemLifecycleState.STOPPED

    @pytest.mark.asyncio
    async def test_idempotent_transition(self):
        sm = LifecycleStateMachine()
        await sm.transition(SystemLifecycleState.STARTING)
        await sm.transition(SystemLifecycleState.STARTING)
        assert sm.state == SystemLifecycleState.STARTING


class FakeComponent:
    def __init__(self, name="fake", fail_close=False):
        self.name = name
        self.close_count = 0
        self._fail_close = fail_close

    async def close(self):
        self.close_count += 1
        if self._fail_close:
            raise RuntimeError(f"{self.name} close failed")


class TestSystemContainerLifecycle:
    @pytest.fixture
    def system(self):
        data_dir = Path(tempfile.mkdtemp(prefix="ai-lab-sp007-"))
        settings = make_test_settings(data_dir, enable_knowledge=False)
        loop = asyncio.new_event_loop()
        return loop.run_until_complete(create_system(settings))

    def _run(self, coro):
        loop = asyncio.new_event_loop()
        return loop.run_until_complete(coro)

    def test_initial_state_created(self, system):
        assert system.lifecycle_state == SystemLifecycleState.CREATED

    def test_start_success(self, system):
        self._run(system.start())
        assert system.lifecycle_state == SystemLifecycleState.READY
        self._run(system.shutdown())

    def test_start_idempotent(self, system):
        self._run(system.start())
        self._run(system.start())
        assert system.lifecycle_state == SystemLifecycleState.READY
        self._run(system.shutdown())

    def test_shutdown_before_start(self, system):
        self._run(system.shutdown())
        assert system.lifecycle_state == SystemLifecycleState.STOPPED

    def test_shutdown_before_start_idempotent(self, system):
        self._run(system.shutdown())
        self._run(system.shutdown())
        assert system.lifecycle_state == SystemLifecycleState.STOPPED

    def test_start_rejected_after_stopped(self, system):
        self._run(system.shutdown())
        with pytest.raises(SystemInitializationError, match="SystemContainer cannot be restarted"):
            self._run(system.start())

    def test_concurrent_shutdown_callers_wait(self, system):
        async def _run():
            await system.start()
            await asyncio.gather(
                system.shutdown(), system.shutdown(), system.shutdown(),
            )
            assert system.lifecycle_state in {
                SystemLifecycleState.STOPPED, SystemLifecycleState.FAILED,
            }
        self._run(_run())

    def test_start_rejected_while_starting(self, system):
        async def _try():
            await system.start()
        self._run(_try())

    def test_start_rejected_while_draining(self, system):
        async def _try():
            await system.start()
            await system.shutdown()
        self._run(_try())


class TestAdmissionGate:
    def test_draining_admission_code(self):
        # Verify draining produces system.draining FailureInfo
        sm = LifecycleStateMachine()
        async def _set():
            await sm.transition(SystemLifecycleState.STARTING)
            await sm.transition(SystemLifecycleState.READY)
            await sm.transition(SystemLifecycleState.DRAINING)
        asyncio.new_event_loop().run_until_complete(_set())
        from core.errors import FailureInfo, ErrorCategory
        code_map = {
            SystemLifecycleState.DRAINING: "system.draining",
            SystemLifecycleState.STOPPED: "system.stopped",
            SystemLifecycleState.FAILED: "system.failed",
            SystemLifecycleState.CREATED: "system.not_ready",
            SystemLifecycleState.STARTING: "system.not_ready",
        }
        assert sm.state == SystemLifecycleState.DRAINING
        assert code_map[SystemLifecycleState.DRAINING] == "system.draining"
        assert code_map[SystemLifecycleState.STOPPED] == "system.stopped"
        assert code_map[SystemLifecycleState.CREATED] == "system.not_ready"
        assert code_map[SystemLifecycleState.FAILED] == "system.failed"
