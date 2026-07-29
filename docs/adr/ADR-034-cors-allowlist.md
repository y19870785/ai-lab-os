# ADR-034：CORS Allowlist 策略

## 状态

Accepted

## 背景

API 过去使用 `allow_origins=["*"]`，允许任意浏览器 Origin 访问 API endpoint。这对
浏览器集成并不安全。

## 决策

使用集中配置的显式 CORS allowlist。

### 策略

1. 默认不允许任何 Origin，即隐式 deny-all；
2. 从逗号分隔的 `AI_LAB_API_ALLOWED_ORIGINS` 解析允许列表；
3. 去除空白，并以不区分大小写的方式去重；
4. 启用身份认证时拒绝通配符 `*`；
5. CLI 和直接 HTTP 等非浏览器调用方不受影响；
6. CORS 与身份认证配置一起保存在 `ApiSecurityConfig`。

### 理由

- 浏览器请求可能携带用户 Session 与 Cookie；通配 CORS 会破坏同源约束；
- 显式 Origin 使允许的调用方可观察、可审计；
- Service-to-service 调用使用 Authorization header，不需要 CORS preflight。

## 后果

- 浏览器消费方必须显式加入 allowlist；
- Preflight（OPTIONS）响应遵循配置的 Origin 列表。
