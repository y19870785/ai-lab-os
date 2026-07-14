import pytest

from core.bus.bus import MemoryBus
from core.task.models import TaskRequest, TaskStatus
from core.task.runtime import TaskRuntime
from core.workflow.models import WorkflowResult, WorkflowStatus


pytestmark = pytest.mark.asyncio(loop_scope="function")


class SequencedWorkflowRuntime:
    def __init__(self, failures=None):
        self.failures = dict(failures or {})
        self.calls = []

    async def run(self, request):
        self.calls.append(request.workflow_name)
        remaining = self.failures.get(request.workflow_name, 0)
        if remaining:
            self.failures[request.workflow_name] = remaining - 1
            raise RuntimeError(f"{request.workflow_name} unavailable")
        return WorkflowResult(
            workflow_id=request.workflow_name,
            status=WorkflowStatus.COMPLETED,
            outputs={"workflow": request.workflow_name},
        )


async def test_retry_repeats_same_workflow_before_advancing():
    workflows = SequencedWorkflowRuntime({"first": 1})
    runtime = TaskRuntime(workflow_runtime=workflows)
    task = await runtime.create_task(TaskRequest(
        task_name="retry",
        workflow_names=["first", "second"],
        max_retries=1,
    ))

    result = await runtime.run(task.id)

    assert workflows.calls == ["first", "first", "second"]
    assert result.status == TaskStatus.COMPLETED
    assert result.retry_count == 1
    assert result.errors == []
    assert result.failure is None


async def test_retry_exhaustion_is_terminal_failed_and_checkpoint_does_not_advance():
    workflows = SequencedWorkflowRuntime({"first": 10})
    runtime = TaskRuntime(workflow_runtime=workflows)
    task = await runtime.create_task(TaskRequest(
        task_name="exhausted",
        workflow_names=["first", "second"],
        max_retries=2,
        trace_id="task-trace",
    ))

    result = await runtime.run(task.id)

    assert workflows.calls == ["first", "first", "first"]
    assert result.status == TaskStatus.FAILED
    assert result.failure is not None
    assert result.failure.code == "task.workflow.execution_failed"
    assert result.trace_id == "task-trace"
    assert "second" not in workflows.calls
    checkpoint = runtime._checkpoint_mgr.load(task.id)
    assert checkpoint is None or checkpoint.current_workflow_index == 0
    assert runtime._manager.get_status(task.id) == TaskStatus.FAILED


async def test_empty_plan_returns_structured_non_retryable_failure():
    runtime = TaskRuntime(workflow_runtime=SequencedWorkflowRuntime())
    task = await runtime.create_task(TaskRequest(task_name="empty"))

    result = await runtime.run(task.id)

    assert result.status == TaskStatus.FAILED
    assert result.failure is not None
    assert result.failure.code == "task.plan.empty"
    assert result.retryable is False


async def test_retry_event_contains_accurate_attempt_and_failure_envelope():
    bus = MemoryBus()
    events = []

    async def collect(event):
        events.append(event)

    await bus.start()
    await bus.subscribe("task.retry", collect)
    try:
        runtime = TaskRuntime(
            workflow_runtime=SequencedWorkflowRuntime({"first": 1}),
            bus=bus,
        )
        task = await runtime.create_task(TaskRequest(
            task_name="events",
            workflow_names=["first"],
            max_retries=1,
            trace_id="retry-trace",
        ))
        result = await runtime.run(task.id)
    finally:
        await bus.stop()

    assert result.status == TaskStatus.COMPLETED
    assert len(events) == 1
    payload = events[0].payload
    assert payload["attempt"] == 1
    assert payload["next_attempt"] == 2
    assert payload["code"] == "task.workflow.execution_failed"
    assert payload["trace_id"] == "retry-trace"
