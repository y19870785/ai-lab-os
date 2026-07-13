"""Workflow 异常定义"""

class WorkflowError(Exception):
    """Workflow 基础异常"""
    pass

class WorkflowNotFoundError(WorkflowError):
    """Workflow 未注册"""
    pass

class WorkflowStateError(WorkflowError):
    """非法状态转换"""
    pass

class WorkflowExecutionError(WorkflowError):
    """执行失败"""
    pass

class WorkflowTimeoutError(WorkflowError):
    """执行超时"""
    pass

class WorkflowCancelledError(WorkflowError):
    """被取消"""
    pass

class StepExecutionError(WorkflowError):
    """步骤执行失败"""
    pass
