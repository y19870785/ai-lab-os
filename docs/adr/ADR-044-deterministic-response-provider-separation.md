# ADR-044：确定性响应与 Provider 提示分离

**状态：** Accepted
**日期：** 2026-07-17

## 验收记录

- 由 SP-011 Accepted；
- PR：#23；
- Approved Head：`beb99115dd273a9fe55e86d21e65f714e7f7f52f`；
- Merge Commit：`5c4b442b2b5c7f934ac381020ba8b310976d5d3a`；
- Accepted Date：2026-07-17。

## 背景

CEO Assistant 过去会在每个成功答案后追加 Provider mode 提示。Reminder 解析、列表、
详情、取消与重新计划是确定性 Service 操作，不调用 LLM，因此这些路径上的 Provider
提示是不准确的产品输出。

## 决策

完全由确定性 Reminder handler 生成的 Application response 携带内部 deterministic
marker。公共响应组装步骤在添加 Mock Provider 提示前检查该 marker。普通 LLM Chat 在
显式 Mock mode 下仍保留既有提示。

该区分在响应组装处完成，不通过字符串替换、路由专用清理或 Presentation 隐藏实现。
确定性 handler 只能报告持久化 Service 返回的字段。

## 后果

- Reminder 响应不再包含无关 Provider 配置文本；
- 实际 LLM-backed Chat 仍明确展示 Mock LLM 行为；
- Marker 只属于 Application response，不创建第二种 Provider mode，也不绕过失败。
