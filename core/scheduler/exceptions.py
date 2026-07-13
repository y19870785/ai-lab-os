"""Scheduler 异常定义"""

class SchedulerError(Exception):
    """Scheduler 基础异常"""
    pass

class JobNotFoundError(SchedulerError):
    """Job 未找到"""
    pass

class JobAlreadyExistsError(SchedulerError):
    """Job 已存在"""
    pass

class JobStateError(SchedulerError):
    """Job 状态错误（如暂停的 Job 无法启动）"""
    pass

class TriggerError(SchedulerError):
    """Trigger 配置错误"""
    pass

class SchedulerShutdownError(SchedulerError):
    """Scheduler 已关闭"""
    pass
