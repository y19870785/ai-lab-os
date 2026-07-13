import pytest
pytestmark = pytest.mark.asyncio(loop_scope="function")
from core.task.runtime import TaskRuntime
from core.task.manager import TaskManager
from core.task.config import TaskConfig
from core.task.models import TaskRequest, TaskStatus, TaskType

class TestTaskRuntime:
    def _make_runtime(self):
        return TaskRuntime(config=TaskConfig())

    async def test_create_task(self):
        rt = self._make_runtime()
        info = await rt.create_task(TaskRequest(task_name="test-create"))
        assert info.name == "test-create"
        assert rt._manager.exists(info.id)

    async def test_run_without_workflows(self):
        rt = self._make_runtime()
        info = await rt.create_task(TaskRequest(task_name="no-wf"))
        result = await rt.run(info.id)
        assert result.status == TaskStatus.COMPLETED

    async def test_pause_resume(self):
        rt = self._make_runtime()
        info = await rt.create_task(TaskRequest(task_name="pause-test"))
        assert await rt.pause(info.id) is False  # can't pause CREATED

    async def test_cancel(self):
        rt = self._make_runtime()
        info = await rt.create_task(TaskRequest(task_name="cancel-test"))
        assert await rt.cancel(info.id)

    async def test_query(self):
        rt = self._make_runtime()
        info = await rt.create_task(TaskRequest(task_name="query-test"))
        found = await rt.query(info.id)
        assert found is not None
        assert found.name == "query-test"

    async def test_list_tasks(self):
        rt = self._make_runtime()
        for i in range(5):
            await rt.create_task(TaskRequest(task_name=f"list-{i}"))
        tasks = await rt.list_tasks()
        assert len(tasks) == 5

    async def test_destroy(self):
        rt = self._make_runtime()
        info = await rt.create_task(TaskRequest(task_name="destroy-me"))
        assert await rt.destroy(info.id)
        assert await rt.query(info.id) is None

    async def test_retry_from_failed(self):
        rt = self._make_runtime()
        info = await rt.create_task(TaskRequest(task_name="retry-test"))
        await rt.run(info.id)  # complete it
        # can't retry from COMPLETED
        assert await rt.retry(info.id) is False
