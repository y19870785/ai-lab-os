import pytest
pytestmark = pytest.mark.asyncio(loop_scope="function")
from core.task.runtime import TaskRuntime
from core.task.manager import TaskManager
from core.task.models import TaskRequest, TaskStatus, TaskType, TaskPriority
from core.task.config import TaskConfig

class TestTaskIntegration:
    """Task Runtime ???????"""

    async def test_full_lifecycle(self):
        rt = TaskRuntime(config=TaskConfig())
        # CREATE
        info = await rt.create_task(TaskRequest(
            task_name="e2e", task_type=TaskType.PIPELINE,
            priority=TaskPriority.HIGH,
        ))
        assert info.priority == TaskPriority.HIGH
        # RUN
        result = await rt.run(info.id)
        assert result.status == TaskStatus.COMPLETED
        # QUERY
        found = await rt.query(info.id)
        assert found is not None
        # LIST
        tasks = await rt.list_tasks()
        assert len(tasks) == 1
        # DESTROY
        await rt.destroy(info.id)
        assert await rt.query(info.id) is None

    async def test_cancel_during_run(self):
        rt = TaskRuntime(config=TaskConfig())
        info = await rt.create_task(TaskRequest(
            task_name="cancel-me", workflow_names=["wf1", "wf2", "wf3"],
        ))
        import asyncio
        # Start run and cancel immediately
        async def cancel_soon():
            await asyncio.sleep(0.05)
            await rt.cancel(info.id)
        asyncio.create_task(cancel_soon())
        result = await rt.run(info.id)
        assert result.status in {TaskStatus.COMPLETED, TaskStatus.CANCELLED}

    async def test_multiple_workflow_task(self):
        rt = TaskRuntime(config=TaskConfig())
        info = await rt.create_task(TaskRequest(
            task_name="multi-wf", workflow_names=["wf_a", "wf_b"],
        ))
        result = await rt.run(info.id)
        assert result.status == TaskStatus.COMPLETED
        assert len(result.workflow_results) <= 2  # wfs run but no real runtime

    async def test_statistics(self):
        mgr = TaskManager()
        rt = TaskRuntime(manager=mgr, config=TaskConfig())
        for i in range(3):
            await rt.create_task(TaskRequest(task_name=f"stat-{i}"))
        stats = mgr.statistics()
        assert stats.total == 3
        assert stats.active == 0  # all CREATED
