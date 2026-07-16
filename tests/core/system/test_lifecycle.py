"""System lifecycle tests with concurrency barriers and real admission gate."""

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
from core.errors import ErrorCategory, FailureException


class TestLifecycleStateMachine:
    def test_initial_state_is_created(self):
        sm = LifecycleStateMachine()
        assert sm.state == SystemLifecycleState.CREATED

    @pytest.mark.asyncio
    async def test_created_to_stopped(self):
        sm = LifecycleStateMachine()
        await sm.transition(SystemLifecycleState.STOPPED)
        assert sm.state == SystemLifecycleState.STOPPED

    @pytest.mark.asyncio
    async def test_invalid_transition_raises(self):
        sm = LifecycleStateMachine()
        with pytest.raises(InvalidLifecycleTransitionError):
            await sm.transition(SystemLifecycleState.READY)


class TestSystemContainerLifecycle:
    @pytest.fixture
    def system(self):
        data_dir = Path(tempfile.mkdtemp(prefix="ai-lab-sp007-"))
        settings = make_test_settings(data_dir, enable_knowledge=False)
        return asyncio.new_event_loop().run_until_complete(create_system(settings))

    def test_start_success(self, system):
        loop = asyncio.new_event_loop()
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

    def test_start_rejected_after_stopped(self, system):
        loop = asyncio.new_event_loop()
        loop.run_until_complete(system.shutdown())
        with pytest.raises(SystemInitializationError, match="cannot be restarted"):
            loop.run_until_complete(system.start())

    def test_concurrent_shutdown_all_wait(self, system):
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


class TestAdmissionGate:
    @pytest.fixture
    def system(self):
        data_dir = Path(tempfile.mkdtemp(prefix="ai-lab-sp007-"))
        settings = make_test_settings(data_dir, enable_knowledge=False)
        return asyncio.new_event_loop().run_until_complete(create_system(settings))

    def test_ready_no_exception(self, system):
        loop = asyncio.new_event_loop()
        loop.run_until_complete(system.start())
        try:
            system.ensure_accepting_work()
        finally:
            loop.run_until_complete(system.shutdown())

    def test_draining_admission(self, system):
        loop = asyncio.new_event_loop()
        loop.run_until_complete(system.start())
        loop.run_until_complete(system.shutdown())
        with pytest.raises(FailureException) as exc_info:
            system.ensure_accepting_work()
        f = exc_info.value.failure
        assert f.code == "system.stopped"
        assert f.category == ErrorCategory.UNAVAILABLE
        assert f.component == "system.lifecycle"
        assert f.operation == "admit_request"
        assert f.retryable is True

    def test_not_ready_admission(self, system):
        with pytest.raises(FailureException) as exc_info:
            system.ensure_accepting_work()
        f = exc_info.value.failure
        assert f.code == "system.not_ready"
        assert f.category == ErrorCategory.UNAVAILABLE
