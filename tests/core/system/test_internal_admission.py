"""Behavioral tests for the canonical internal work admission boundary."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from applications.ceo_assistant.application import CEOAssistant
from applications.models import (
    ApplicationInfo,
    ApplicationManifest,
    ApplicationRequest,
    ApplicationResponse,
)
from applications.registry import ApplicationRegistry
from applications.runtime import ApplicationRuntime
from core.errors import ErrorCategory, FailureException
from core.scheduler.config import SchedulerConfig
from core.scheduler.models import JobRun, JobRunStatus, ScheduleRequest, Trigger, TriggerType
from core.scheduler.runtime import SchedulerRuntime
from core.system import create_system, make_test_settings
from core.system.admission import WorkAdmissionGate
from core.system.lifecycle import LifecycleStateMachine, SystemLifecycleState


pytestmark = pytest.mark.asyncio(loop_scope="function")


async def _lifecycle_at(state: SystemLifecycleState) -> LifecycleStateMachine:
    lifecycle = LifecycleStateMachine()
    if state == SystemLifecycleState.CREATED:
        return lifecycle
    await lifecycle.transition(SystemLifecycleState.STARTING)
    if state == SystemLifecycleState.STARTING:
        return lifecycle
    await lifecycle.transition(SystemLifecycleState.READY)
    if state == SystemLifecycleState.READY:
        return lifecycle
    await lifecycle.transition(SystemLifecycleState.DRAINING)
    if state == SystemLifecycleState.DRAINING:
        return lifecycle
    await lifecycle.transition(state)
    return lifecycle


class CountingAdmissionGate(WorkAdmissionGate):
    def __init__(self, lifecycle: LifecycleStateMachine) -> None:
        super().__init__(lifecycle)
        self.lifecycle_checks = 0

    def _check_lifecycle(self) -> None:
        self.lifecycle_checks += 1
        super()._check_lifecycle()


class NestedGatedApplication:
    def __init__(self, admission: WorkAdmissionGate) -> None:
        self._admission = admission
        self.calls = 0
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.block = False

    async def run(self, request: ApplicationRequest) -> ApplicationResponse:
        with self._admission.admit():
            self.calls += 1
            self.started.set()
            if self.block:
                await self.release.wait()
            return ApplicationResponse(answer=request.user_input, mode="mock")


def _runtime(admission: WorkAdmissionGate, app: NestedGatedApplication):
    registry = ApplicationRegistry()
    registry.register(
        ApplicationInfo(name="test"),
        ApplicationManifest(name="test", entrypoint="test"),
        instance=app,
    )
    return ApplicationRuntime(registry=registry, admission=admission)


@pytest.mark.parametrize(
    ("state", "code"),
    [
        (SystemLifecycleState.CREATED, "system.not_ready"),
        (SystemLifecycleState.STARTING, "system.not_ready"),
        (SystemLifecycleState.DRAINING, "system.draining"),
        (SystemLifecycleState.STOPPED, "system.stopped"),
        (SystemLifecycleState.FAILED, "system.failed"),
    ],
)
async def test_gate_reuses_complete_lifecycle_failure_contract(state, code):
    gate = WorkAdmissionGate(await _lifecycle_at(state))

    with pytest.raises(FailureException) as exc_info:
        gate.ensure_accepting_work()

    failure = exc_info.value.failure
    assert failure.code == code
    assert failure.category == ErrorCategory.UNAVAILABLE
    assert failure.component == "system.lifecycle"
    assert failure.operation == "admit_request"
    assert failure.retryable is True


async def test_ready_gate_accepts_work_without_io_or_await():
    gate = WorkAdmissionGate(await _lifecycle_at(SystemLifecycleState.READY))
    gate.ensure_accepting_work()


async def test_application_and_nested_handler_check_lifecycle_exactly_once():
    lifecycle = await _lifecycle_at(SystemLifecycleState.READY)
    gate = CountingAdmissionGate(lifecycle)
    app = NestedGatedApplication(gate)
    runtime = _runtime(gate, app)
    await runtime.initialize()

    response = await runtime.execute(
        ApplicationRequest(application_name="test", user_input="accepted")
    )

    assert response.answer == "accepted"
    assert app.calls == 1
    assert gate.lifecycle_checks == 1


async def test_accepted_work_finishes_after_lifecycle_enters_draining():
    lifecycle = await _lifecycle_at(SystemLifecycleState.READY)
    gate = CountingAdmissionGate(lifecycle)
    app = NestedGatedApplication(gate)
    app.block = True
    runtime = _runtime(gate, app)
    await runtime.initialize()

    work = asyncio.create_task(runtime.execute(
        ApplicationRequest(application_name="test", user_input="in-flight")
    ))
    await app.started.wait()
    await lifecycle.transition(SystemLifecycleState.DRAINING)
    app.release.set()

    response = await work
    assert response.answer == "in-flight"
    assert app.calls == 1
    assert gate.lifecycle_checks == 1


async def test_detached_child_cannot_start_new_work_after_parent_scope_ends():
    lifecycle = await _lifecycle_at(SystemLifecycleState.READY)
    gate = WorkAdmissionGate(lifecycle)
    side_effects = 0
    child_created = asyncio.Event()
    release_child = asyncio.Event()
    detached_task: asyncio.Task | None = None

    class NewWorkApplication:
        async def run(self, request):
            nonlocal side_effects
            side_effects += 1
            return ApplicationResponse(answer="unexpected", mode="mock")

    class OuterApplication:
        def __init__(self) -> None:
            self.runtime: ApplicationRuntime | None = None

        async def run(self, request):
            nonlocal detached_task

            async def detached_new_work():
                child_created.set()
                await release_child.wait()
                assert self.runtime is not None
                return await self.runtime.execute(ApplicationRequest(
                    application_name="new-work",
                    user_input="must be readmitted",
                ))

            detached_task = asyncio.create_task(detached_new_work())
            await child_created.wait()
            return ApplicationResponse(answer="outer complete", mode="mock")

    registry = ApplicationRegistry()
    outer = OuterApplication()
    registry.register(
        ApplicationInfo(name="outer"),
        ApplicationManifest(name="outer", entrypoint="outer"),
        instance=outer,
    )
    registry.register(
        ApplicationInfo(name="new-work"),
        ApplicationManifest(name="new-work", entrypoint="new-work"),
        instance=NewWorkApplication(),
    )
    runtime = ApplicationRuntime(registry=registry, admission=gate)
    outer.runtime = runtime
    await runtime.initialize()

    response = await runtime.execute(ApplicationRequest(
        application_name="outer",
        user_input="create detached child",
    ))
    assert response.answer == "outer complete"
    assert detached_task is not None

    await lifecycle.transition(SystemLifecycleState.DRAINING)
    release_child.set()
    with pytest.raises(FailureException) as exc_info:
        await detached_task

    assert exc_info.value.failure.code == "system.draining"
    assert side_effects == 0


@pytest.mark.parametrize(
    ("state", "code"),
    [
        (SystemLifecycleState.DRAINING, "system.draining"),
        (SystemLifecycleState.STOPPED, "system.stopped"),
        (SystemLifecycleState.FAILED, "system.failed"),
    ],
)
async def test_application_runtime_rejects_before_handler_side_effect(state, code):
    gate = WorkAdmissionGate(await _lifecycle_at(state))
    app = NestedGatedApplication(gate)
    runtime = _runtime(gate, app)
    await runtime.initialize()

    with pytest.raises(FailureException) as exc_info:
        await runtime.execute(ApplicationRequest(application_name="test", user_input="no"))

    assert exc_info.value.failure.code == code
    assert app.calls == 0


@pytest.mark.parametrize(
    ("state", "code"),
    [
        (SystemLifecycleState.DRAINING, "system.draining"),
        (SystemLifecycleState.STOPPED, "system.stopped"),
        (SystemLifecycleState.FAILED, "system.failed"),
    ],
)
async def test_direct_ceo_assistant_entrypoint_rejects_before_handler(state, code):
    gate = WorkAdmissionGate(await _lifecycle_at(state))
    assistant = CEOAssistant(admission=gate)
    calls = 0

    async def accepted_handler(request):
        nonlocal calls
        calls += 1
        return ApplicationResponse(answer="unexpected", mode="mock")

    assistant._run_accepted = accepted_handler
    with pytest.raises(FailureException) as exc_info:
        await assistant.run(ApplicationRequest(
            application_name="ceo-assistant", user_input="no"
        ))

    assert exc_info.value.failure.code == code
    assert calls == 0


class CountingJobExecutor:
    def __init__(self) -> None:
        self.calls = 0

    async def execute(self, job, run):
        self.calls += 1
        return run.model_copy(update={
            "status": JobRunStatus.SUCCESS,
            "finished_at": datetime.now(timezone.utc),
        })


async def test_scheduler_does_not_claim_or_dispatch_after_draining():
    lifecycle = await _lifecycle_at(SystemLifecycleState.READY)
    gate = WorkAdmissionGate(lifecycle)
    executor = CountingJobExecutor()
    scheduler = SchedulerRuntime(
        executor=executor,
        config=SchedulerConfig(persistence_enabled=False),
        admission=gate,
    )
    job = await scheduler.schedule(ScheduleRequest(
        job_name="blocked-due-job",
        workflow_name="workflow",
        trigger=Trigger(
            trigger_type=TriggerType.ONE_SHOT,
            run_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        ),
    ))
    await lifecycle.transition(SystemLifecycleState.DRAINING)

    await scheduler._tick()

    assert executor.calls == 0
    assert job.run_count == 0
    assert not scheduler._background_tasks


async def test_scheduler_does_not_claim_or_persist_run_after_draining():
    lifecycle = await _lifecycle_at(SystemLifecycleState.READY)
    gate = WorkAdmissionGate(lifecycle)
    executor = CountingJobExecutor()

    class RecordingPersistence:
        def __init__(self) -> None:
            self.jobs = []
            self.claim_calls = 0
            self.finalize_calls = 0

        async def save_job(self, job):
            self.jobs = [job]

        async def release_expired_claims(self, now, *, retry_delay_seconds):
            return 0

        async def load_jobs(self):
            return self.jobs

        async def claim_job(self, *args, **kwargs):
            self.claim_calls += 1
            return None

        async def finalize_claim(self, *args, **kwargs):
            self.finalize_calls += 1

    persistence = RecordingPersistence()
    scheduler = SchedulerRuntime(
        executor=executor,
        persistence=persistence,
        config=SchedulerConfig(persistence_enabled=True),
        admission=gate,
    )
    await scheduler.schedule(ScheduleRequest(
        job_name="blocked-persisted-job",
        workflow_name="workflow",
        trigger=Trigger(
            trigger_type=TriggerType.ONE_SHOT,
            run_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        ),
    ))
    await lifecycle.transition(SystemLifecycleState.DRAINING)

    await scheduler._tick()

    assert persistence.claim_calls == 0
    assert persistence.finalize_calls == 0
    assert executor.calls == 0
    assert not scheduler._background_tasks


async def test_core_system_public_imports_remain_available(tmp_path):
    from core.system import (
        SystemContainer,
        SystemSettings,
        create_system as public_create_system,
        load_system_settings,
        make_test_settings as public_make_test_settings,
    )

    assert SystemContainer.__name__ == "SystemContainer"
    assert SystemSettings.__name__ == "SystemSettings"
    assert callable(public_create_system)
    assert callable(load_system_settings)
    assert public_make_test_settings(tmp_path).environment == "test"


async def test_factory_wires_one_gate_to_all_production_entrypoints(tmp_path):
    system = await create_system(make_test_settings(
        tmp_path,
        enable_scheduler=True,
        enable_reminders=False,
    ))

    assert system.application_runtime._admission is system.work_admission_gate
    assert system.ceo_assistant._admission is system.work_admission_gate
    assert system.scheduler_runtime is not None
    assert system.scheduler_runtime._admission is system.work_admission_gate
    assert system.work_admission_gate._lifecycle is system._lifecycle

    await system.start()
    try:
        response = await system.application_runtime.execute(ApplicationRequest(
            application_name="ceo-assistant", user_input="hello"
        ))
        assert response.status == "ok"
    finally:
        await system.shutdown()
