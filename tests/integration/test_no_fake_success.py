"""Critical paths must expose missing dependencies instead of faking success."""

import pytest

from applications.exceptions import ApplicationNotRegisteredError
from applications.models import ApplicationRequest
from applications.runtime import ApplicationRuntime
from core.agents.executor import AgentExecutor
from core.agents.models import AgentInfo, AgentRequest
from core.scheduler.jobs import JobExecutor
from core.scheduler.models import Job, JobInfo, JobRunStatus
from core.task.models import TaskRequest, TaskStatus
from core.task.runtime import TaskRuntime

pytestmark = pytest.mark.asyncio(loop_scope="function")


async def test_unregistered_application_fails_explicitly():
    runtime = ApplicationRuntime()
    await runtime.initialize()
    with pytest.raises(ApplicationNotRegisteredError):
        await runtime.execute(ApplicationRequest(application_name="missing", user_input="hello"))


async def test_agent_without_llm_returns_error_not_echo():
    response = await AgentExecutor(AgentInfo(name="no-llm")).execute(
        AgentRequest(user_input="hello", memory_enabled=False)
    )
    assert response.status == "error"
    assert "Echo" not in response.answer
    assert "not configured" in response.answer


async def test_scheduler_job_without_workflow_is_failed():
    run = await JobExecutor(workflow_runtime=None).execute(
        Job(info=JobInfo(name="missing-runtime"), workflow_name="missing")
    )
    assert run.status == JobRunStatus.FAILED
    assert "not configured" in run.error


async def test_task_with_workflows_without_runtime_is_failed():
    runtime = TaskRuntime(workflow_runtime=None)
    task = await runtime.create_task(TaskRequest(
        task_name="missing-runtime",
        variables={"workflow_names": ["required-workflow"]},
    ))
    result = await runtime.run(task.id)
    assert result.status == TaskStatus.FAILED
    assert "not configured" in result.errors[0]
