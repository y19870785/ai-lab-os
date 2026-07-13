"""TaskDependencyResolver —— 解析 Task 间依赖关系。

支持 AFTER / BEFORE / ALL_SUCCESS / ANY_SUCCESS / ALL_FAILED / ANY_FAILED / MANUAL。
"""

from __future__ import annotations
from core.task.models import TaskDependency, DependencyType, TaskStatus


class DependencyResolver:
    """Task 依赖解析器 —— 纯函数，无副作用"""

    @staticmethod
    def is_satisfied(dep: TaskDependency, dependee_status: TaskStatus) -> bool:
        """判断依赖是否满足"""
        dt = dep.dependency_type
        if dt == DependencyType.AFTER:
            return dependee_status in {TaskStatus.COMPLETED, TaskStatus.FAILED,
                                       TaskStatus.CANCELLED, TaskStatus.TIMEOUT}
        elif dt == DependencyType.BEFORE:
            return dependee_status == TaskStatus.CREATED
        elif dt == DependencyType.ALL_SUCCESS:
            return dependee_status == TaskStatus.COMPLETED
        elif dt == DependencyType.ANY_SUCCESS:
            return dependee_status == TaskStatus.COMPLETED
        elif dt == DependencyType.ALL_FAILED:
            return dependee_status == TaskStatus.FAILED
        elif dt == DependencyType.ANY_FAILED:
            return dependee_status == TaskStatus.FAILED
        elif dt == DependencyType.MANUAL:
            return False  # 永远不自动满足，需手动触发
        return False

    @staticmethod
    def are_all_satisfied(deps: list[TaskDependency],
                          statuses: dict[str, TaskStatus]) -> bool:
        """检查所有依赖是否满足"""
        for dep in deps:
            status = statuses.get(dep.depends_on_task_id)
            if status is None:
                return False
            if not DependencyResolver.is_satisfied(dep, status):
                return False
        return True

    @staticmethod
    def any_failure(deps: list[TaskDependency],
                    statuses: dict[str, TaskStatus]) -> bool:
        """检查是否有依赖失败（用于提前终止）"""
        for dep in deps:
            if dep.dependency_type in {DependencyType.ALL_SUCCESS, DependencyType.ANY_SUCCESS}:
                status = statuses.get(dep.depends_on_task_id)
                if status == TaskStatus.FAILED:
                    return True
        return False
