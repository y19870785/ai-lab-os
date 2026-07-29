# ADR-033：API 身份认证机制

## 状态

Accepted

## 背景

AI-Lab API 过去允许未经身份认证访问所有 endpoint。系统从 prototype 进入 alpha 后，
必须控制 API 访问。

## 决策

使用一个集中配置的静态 Bearer token 完成 API 身份认证。

### 身份认证流程

1. 创建应用时，由 `SystemSettings` 构建 `ApiSecurityConfig`；
2. `Authenticator` 使用 `hmac.compare_digest` 验证
   `Authorization: Bearer <token>`；
3. 受保护 Router 在 Router 层加入 `Depends(require_auth)`；
4. 认证失败返回 HTTP 401、`ErrorCategory.UNAUTHENTICATED` 和标准
   `WWW-Authenticate: Bearer` 语义；
5. Token 不得写入日志或错误响应。

### 配置

- `AI_LAB_API_AUTH_ENABLED`：布尔值，默认 `True`；
- `AI_LAB_API_TOKEN`：Bearer token，默认为空；
- 启用认证但没有 token 时，应用构建失败。

## 已考虑的替代方案

- **JWT/OAuth**：对单租户 alpha 过于复杂，延期处理；
- **IP allowlist**：在动态环境中脆弱，只能补充认证，不能替代；
- **零认证 / 仅信任网络**：任何远程暴露场景都不可接受。

## 后果

- 消费方首次集成必须显式配置 token；
- Token rotation 需要修改配置并重启；
- 本阶段不提供用户级或基于角色的访问差异。
