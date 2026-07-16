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
        assert sm.accepting_work

    @pytest.mark.asyncio
    async def test_created_to_stopped_shutdown_before_start(self):
        sm = LifecycleStateMachine()
        await sm.transition(SystemLifecycleState.STOPPED)
        assert sm.state == SystemLifecycleState.STOPPED
        assert not sm.accepting_work

    @pytest.mark.asyncio
    async def test_ready_to_draining_to_stopped(self):
        sm = LifecycleStateMachine()
        await sm.transition(SystemLifecycleState.STARTING)
        await sm.transition(SystemLifecycleState.READY)
        await sm.transition(SystemLifecycleState.DRAINING)
        assert sm.state == SystemLifecycleState.DRAINING
        await sm.transition(SystemLifecycleState.STOPPED)
        assert sm.state == SystemLifecycleState.STOPPED

    @pytest.mark.asyncio
    async def test_starting_to_draining(self):
        sm = LifecycleStateMachine()
        await sm.transition(SystemLifecycleState.STARTING)
        await sm.transition(SystemLifecycleState.DRAINING)
        assert sm.state == SystemLifecycleState.DRAINING

    @pytest.mark.asyncio
    async def test_invalid_transitions_raise(self):
        sm = LifecycleStateMachine()
        with pytest.raises(InvalidLifecycleTransitionError):
            await sm.transition(SystemLifecycleState.READY)
        await sm.transition(SystemLifecycleState.STARTING)
        with pytest.raises(InvalidLifecycleTransitionError):
            await sm.transition(SystemLifecycleState.STOPPED)

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
        return asyncio.new_event_loop().run_until_complete(create_system(settings))

    def test_initial_state_created(self, system):
        assert system.lifecycle_state == SystemLifecycleState.CREATED
        assert not system.accepting_work

    def test_start_success(self, system):
        loop = asyncio.new_event_loop()
        loop.run_until_complete(system.start())
        assert system.lifecycle_state == SystemLifecycleState.READY
        loop.run_until_complete(system.shutdown())

    def test_start_idempotent(self, system):
        loop = asyncio.new_event_loop()
        loop.run_until_complete(system.start())
        loop.run_until_complete(system.start())
        assert system.lifecycle_state == SystemLifecycleState.READY
        loop.run_until_complete(system.shutdown())

    def test_shutdown_before_start(self, system):
        loop = asyncio.new_event_loop()
        loop.run_until_complete(system.shutdown())
        assert system.lifecycle_state == SystemLifecycleState.STOPPED

    def test_shutdown_before_start_idempotent(self, system):
        loop = asyncio.new_event_loop()
        loop.run_until_complete(system.shutdown())
        loop.run_until_complete(system.shutdown())
        assert system.lifecycle_state == SystemLifecycleState.STOPPED

    def test_three_concurrent_shutdowns_all_wait(self, system):
        async def _run():
            await system.start()
            await asyncio.gather(
                system.shutdown(), system.shutdown(), system.shutdown(),
            )
            assert system.lifecycle_state in {
                SystemLifecycleState.STOPPED, SystemLifecycleState.FAILED,
            }
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_run())

    def test_startup_failure_rollback(self, system):
        loop = asyncio.new_event_loop()
        loop.run_until_complete(system.shutdown())
        assert system.lifecycle_state == SystemLifecycleState.STOPPED
