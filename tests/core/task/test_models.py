import pytest
from core.task.models import (
    TaskInfo, TaskRequest, TaskResult, TaskContext, TaskCheckpoint,
    TaskDependency, TaskStatus, TaskPriority, TaskType, DependencyType,
)

class TestTaskModels:
    def test_task_info(self):
        info = TaskInfo(name="t1", task_type=TaskType.PIPELINE, priority=TaskPriority.HIGH)
        assert info.name == "t1"
        assert info.priority == TaskPriority.HIGH
        assert len(info.id) > 0

    def test_task_request(self):
        req = TaskRequest(task_name="my-task", workflow_names=["wf1", "wf2"],
                          timeout=300, max_retries=5)
        assert req.workflow_names == ["wf1", "wf2"]
        assert req.timeout == 300

    def test_task_result(self):
        r = TaskResult(task_id="t1", status=TaskStatus.COMPLETED,
                       workflow_results={"wf1": "ok"})
        assert r.status == TaskStatus.COMPLETED
        assert r.workflow_results["wf1"] == "ok"

    def test_task_context(self):
        ctx = TaskContext(task_id="t1", variables={"k": "v"},
                          memory_ids=["m1"], workflow_ids=["w1"])
        assert ctx.variables["k"] == "v"
        assert "m1" in ctx.memory_ids

    def test_task_checkpoint(self):
        cp = TaskCheckpoint(task_id="t1", current_workflow_index=2,
                            completed_workflows=["wf1", "wf2"])
        assert cp.current_workflow_index == 2
        assert len(cp.completed_workflows) == 2

    def test_task_dependency(self):
        dep = TaskDependency(depends_on_task_id="t0",
                             dependency_type=DependencyType.ALL_SUCCESS)
        assert dep.dependency_type == DependencyType.ALL_SUCCESS

    def test_status_enum(self):
        assert TaskStatus.CREATED.value == "created"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.COMPLETED.value == "completed"

    def test_dependency_type_enum(self):
        assert DependencyType.AFTER.value == "after"
        assert DependencyType.ANY_FAILED.value == "any_failed"
