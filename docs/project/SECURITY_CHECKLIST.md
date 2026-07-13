# Security Checklist —— v0.30.0

- [x] 请求体大小限制 (10MB)
- [x] Tool 权限检查
- [x] Workspace 隔离校验
- [x] API Key 脱敏 (`mask_api_key`)
- [x] 日志敏感字段过滤 (`sanitize_log`)
- [x] 文件路径安全校验 (`validate_file_path`)
- [x] 错误信息脱敏 (`sanitize_error_message`)
- [x] API 不暴露内部堆栈 (ErrorHandlerMiddleware)
- [ ] 任意 Shell 执行防护 (预留，当前无 Shell 工具)

## 已知缺口

- 无认证系统（用户在 headers 中携带 ID）
- 无速率限制
- 无输入内容过滤
