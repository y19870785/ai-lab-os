"""Task 异常定义"""

class TaskError(Exception):
    """Task 基础异常"""
    pass

class TaskTimeout(TaskError):
    """Task 超时"""
    pass

class TaskCancelled(TaskError):
    """Task 被取消"""
    pass

class TaskPlanningError(TaskError):
    """Task 规划失败"""
    pass

class TaskExecutionError(TaskError):
    """Task 执行失败"""
    pass

class TaskDependencyError(TaskError):
    """Task 依赖未满足"""
    pass

class TaskNotFoundError(TaskError):
    """Task 未找到"""
    pass

class TaskStateError(TaskError):
    """Task 状态转换非法"""
    pass
