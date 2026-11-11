# Telecom AIOps AI Service

通信网络智能运维平台的 Python/FastAPI 智能诊断服务。当前版本提供两条演示路径：

- **本地确定性闭环**：真实调用 Spring Boot 与 MySQL，不调用外部大模型，适合面试现场稳定演示。
- **实时 Agent 闭环**：通过兼容 OpenAI Tool Calling 协议的 DeepSeek 接口，自主选择查询工具并生成诊断结论。

## 架构

```text
用户/Swagger
    |
    v
FastAPI AI Service
    |-- 本地演示编排（无外部模型）
    |-- OpsAgent（LangGraph + DeepSeek Tool Calling）
    |-- PostgreSQL 检查点（独立 telecom_agent 数据库）
    |-- Agent Trace V1
    |
    v
Spring Boot REST API
    |
    v
MySQL：网元、拓扑、KPI、告警、异常、诊断案例
```

大模型不直接访问 MySQL。数据库查询、业务校验和根因候选评分均由 Java 服务完成；Python 负责工具适配、Agent 编排和可观察轨迹。

## 最小可演示场景

场景数据：2026-08-27 17:45–18:10，网元 9、10 两个下游 5G 基站同时出现传输中断。

演示链路：

```text
受影响网元 9、10
→ 查询共同上游 8、7、6
→ Java preview 结合拓扑、告警和异常评分
→ 根因候选：网元 7（福田汇聚交换机 SW1）
→ 查询 OPTICAL_POWER_LOW、LINK_FLAP
→ 查询接收光功率和下游吞吐量
→ 输出证据、置信度、建议与逐步 Trace
```

当前种子数据的预期结果：

- 根因网元：`7 / SEED-AGG-SW1`；
- 根因候选规则分：`0.775`（不是校准后的概率）；
- 接收光功率：`-8.1 dBm → -22.1 dBm`；
- 网元9吞吐量：`242.1 Mbps → 3.8 Mbps`；
- 网元10吞吐量：`228.7 Mbps → 4.1 Mbps`；
- 关键告警：`OPTICAL_POWER_LOW`、`LINK_FLAP`。

## 启动

### 1. 启动 Java 服务

确认 MySQL 的 `telecom_aiops` 数据库已导入后，在 Java 工程目录执行：

```powershell
mvn spring-boot:run
```

Java 服务默认地址为 `http://127.0.0.1:8080`。

### 2. 启动 Python 服务

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

打开 `http://127.0.0.1:8000/docs` 查看 Swagger。

## 演示一：完全本地、只读

在 Swagger 中调用：

```text
GET /api/demo/root-cause
```

这个接口：

- 不调用外部模型；
- 不写数据库；
- 并行查询根因网元、告警、异常和 KPI；
- 对管理 IP、序列号和密钥类字段脱敏；
- 返回每个步骤的状态与耗时。

## 演示二：实时 Tool Calling Agent

仅在明确允许把必要的诊断数据发送到配置的大模型服务时使用。先设置 `DS_API_KEY`，然后调用：

```text
POST /api/agent/chat
```

请求示例：

```json
{
  "message": "2026-08-27 17:45 到 18:10，网元9和10同时出现传输中断。请查询共同上游、告警、异常和诊断预览，给出根因候选、证据、置信度和建议操作。"
}
```

Agent Trace V1 会返回：

- `traceId`；
- 每轮 LLM 调用及耗时；
- 工具名称、参数、结果摘要与错误；
- Token 统计；
- 终止原因；
- 脱敏后的证据链。

Trace 记录的是可观察动作和证据，不记录或声称获取模型隐藏思维链。

## Day 1：可恢复诊断会话（2026-10-20）

新增 `POST /api/agent/sessions`、`POST /api/agent/sessions/{sessionId}/resume`、`GET /api/agent/traces/{traceId}`。这三个接口要求本地开发用的 `X-Agent-Key`，从私有 `.env.agent` 读取配置；不要提交或展示此文件。旧 `/api/agent/chat` 保留兼容，不提供完整的会话入口校验流程。

诊断图为：提取请求 → 参数校验 → 模型决策 ↔ 工具执行 → 输出。缺少参数时通过 interrupt 暂停；模型提取的完整参数需用户确认。检查点保存可恢复的状态，Trace JSON 保存可观察动作，两者作用不同。

工具已增至9个，包括 KPI 可用指标发现与指定窗口异常查询。KPI 数据仍由 Java 查询 MySQL，尚未迁移到 TimescaleDB。

新增本地验证（不调用外部模型）：

```powershell
.\.venv\Scripts\python.exe backend_integration.py
.\.venv\Scripts\python.exe checkpoint_smoke.py create
# 使用上一步会话 ID 在另一个进程恢复：
.\.venv\Scripts\python.exe checkpoint_smoke.py resume <sessionId>
```

27项自动化测试及本地后端集成已通过；真实 DeepSeek 新流程回归尚待数据外发授权，不能据此声称模型诊断效果已提升。

## 自动化测试

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

当前测试覆盖：

- 单工具成功后生成最终答案；
- Trace 敏感字段脱敏；
- 非法 JSON 工具参数隔离；
- 最大轮数终止状态；
- 大结果截断。

## 当前边界

- 本地演示使用固定种子故障，不代表完整生产故障覆盖率；
- Java 根因评分当前为确定性混合规则，不是大模型自行计算；
- Trace 随响应返回并保存为本地 JSON，可通过受保护接口查询；尚无历史查询页面或自动保留期清理；
- 当前是单 Agent + 工具架构，不应表述为已经完成多智能体平台；
- 正式处置操作仍需人工确认，演示不执行数据库写入或设备操作。
