# RFC-016：Application API 安全边界

## 状态

Adopted

## 背景

AI-Lab Application / CEO Assistant API 已进入真实执行链，但 API 缺少统一访问认证，
CORS 允许任意 Origin，网络可达的调用方可以调用业务 API，且调用者身份与 API 信任边界
之间没有明确合同。

SP-006 为 Alpha 开发阶段建立最小且可验证的 API 安全边界。

## 决策

1. 启用身份认证时，Task、Work Log、Reminder、Chat、Application、Decision、Brief、
   Knowledge 与 Workflow 等全部业务 Endpoint 都需要 Bearer token；
2. `/health`、`/health/*` 与 `/metrics` 保持公开；
3. 静态 Bearer token 通过 `AI_LAB_API_TOKEN` 配置，验证使用
   `hmac.compare_digest`；
4. CORS 使用 `AI_LAB_API_ALLOWED_ORIGINS` 显式 allowlist，默认不允许任何 Origin；
   启用认证时，配置阶段拒绝通配符 `*`；
5. 认证实现在 `applications/security/` 集中管理，并通过
   `include_router(dependencies=[Depends(require_auth)])` 应用于 Router 层；
6. 构建应用时验证 Token；启用认证但未配置 Token 时启动失败；
7. `AI_LAB_API_AUTH_ENABLED=false` 必须显式设置，只用于可信本地开发。

## 后果

- 受保护 Endpoint 的消费方必须携带 `Authorization: Bearer <token>`；
- CLI 与非浏览器调用方不受 CORS 限制；
- 缺失或无效 Token 返回 HTTP 401；
- Token 不出现在日志、响应或异常 Detail；
- Auth-disabled mode 仅供测试，生产或远程使用必须启用认证；
- Prompt Injection、多用户 RBAC、JWT/OAuth 与完整 Identity System 不在范围。
