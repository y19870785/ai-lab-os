# Incident Playbook —— v0.31.0 Alpha

## 常见故障处理

### 症状：API 返回 500
1. 检查日志 `logs/ai-lab.log`
2. 确认 API Key 有效
3. 重新启动服务

### 症状：Provider 超时
1. 检查网络连接
2. 增加 `config/alpha.yaml` 中的 timeout
3. 切换到 Mock 模式临时运行

### 症状：Chroma 不可用
1. 检查 `data/chroma/` 目录权限
2. 重启服务恢复 Chroma

### 症状：内存持续增长
1. 检查 Scheduler tick 频率
2. 检查是否有未关闭的 Session
3. 重启释放资源（当前版本无热修复）

### 症状：数据丢失
1. 检查 `data/` 目录挂载
2. 检查 SQLite 文件完整性
3. 从备份恢复（如有）
