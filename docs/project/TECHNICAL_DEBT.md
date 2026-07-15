# 技术债清单

## 开放

| ID | 描述 | 优先级 | 状态 |
|----|------|--------|------|
| TD-001 | 部分测试辅助函数错误传入 id=None，导致 Pydantic default_factory 不触发 | P3 | Open |

## 已解决

| ID | 描述 | 解决版本 |
|----|------|---------|
| TD-001-resolved | 生产代码正常，测试代码已修复 | v0.13.0 |

## 已知限制（非债，属于设计取舍）

| 描述 | 计划解决版本 |
|------|------------|
| Cron 仅支持 */N 格式 | v0.22.0 |
| Event Trigger 未实现 | v0.22.0 |
| Scheduler 单进程 | v0.50.0 |
| SchedulerPersistence 仍独立持有 SQLite connection，尚未迁移 DatabaseManager | 后续独立稳定化任务 |
| Mock Provider 替代真实 API | v0.25.0 |
