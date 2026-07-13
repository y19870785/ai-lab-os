import pytest
from core.task.dependencies import DependencyResolver
from core.task.models import TaskDependency, DependencyType, TaskStatus

class TestDependencyResolver:
    def test_after_satisfied(self):
        dep = TaskDependency(depends_on_task_id="t0", dependency_type=DependencyType.AFTER)
        assert DependencyResolver.is_satisfied(dep, TaskStatus.COMPLETED)
        assert DependencyResolver.is_satisfied(dep, TaskStatus.FAILED)

    def test_after_not_satisfied(self):
        dep = TaskDependency(depends_on_task_id="t0", dependency_type=DependencyType.AFTER)
        assert not DependencyResolver.is_satisfied(dep, TaskStatus.RUNNING)

    def test_all_success(self):
        dep = TaskDependency(dependency_type=DependencyType.ALL_SUCCESS)
        assert DependencyResolver.is_satisfied(dep, TaskStatus.COMPLETED)
        assert not DependencyResolver.is_satisfied(dep, TaskStatus.FAILED)

    def test_manual_never_satisfied(self):
        dep = TaskDependency(dependency_type=DependencyType.MANUAL)
        assert not DependencyResolver.is_satisfied(dep, TaskStatus.COMPLETED)

    def test_are_all_satisfied(self):
        deps = [TaskDependency(depends_on_task_id="t0", dependency_type=DependencyType.AFTER)]
        statuses = {"t0": TaskStatus.COMPLETED}
        assert DependencyResolver.are_all_satisfied(deps, statuses)

    def test_are_all_satisfied_missing(self):
        deps = [TaskDependency(depends_on_task_id="t0", dependency_type=DependencyType.AFTER)]
        assert not DependencyResolver.are_all_satisfied(deps, {})

    def test_any_failure(self):
        deps = [TaskDependency(depends_on_task_id="t0", dependency_type=DependencyType.ALL_SUCCESS)]
        statuses = {"t0": TaskStatus.FAILED}
        assert DependencyResolver.any_failure(deps, statuses)
