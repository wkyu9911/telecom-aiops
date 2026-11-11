import asyncio

from app.agent.graph import build_graph, new_state
from app.agent.trace_store import write_trace
from app.agent.tool_dispatcher import execute_tool
from app.agent.tool_schemas import TOOLS
from app.clients.deepseek_client import deepseek_client
from app.core.config import settings

SYSTEM_PROMPT = """
你是通信网络智能运维平台中的根因分析智能体。

你的职责是根据平台提供的真实网络数据，对网络故障进行分析。

你可以使用工具查询：
- 网络元素信息
- 上下游拓扑
- 多设备共同上游
- KPI统计
- 告警
- 异常事件
- Java根因诊断引擎结果

必须遵守以下规则：

1. 不得虚构数据库中不存在的设备、告警、KPI或异常。
2. 涉及真实网络状态时，应优先调用工具获取数据。
3. 多个设备同时故障时，应优先考虑共同上游拓扑。
4. 拓扑接近并不等于根因，必须结合告警和异常证据。
5. Java诊断引擎的结果是重要证据，但不是唯一证据。
6. 如果数据不足，应明确说明缺少哪些数据，不得强行下结论。
7. 根因分析应区分：
   - 现象
   - 证据
   - 根因候选
   - 置信程度
   - 建议操作
8. 不允许直接修改数据库。
9. 当前阶段只能执行只读分析工具和preview诊断。

最终回答使用中文，并尽量简洁、结构清晰。
"""


class OpsAgent:
    """Single Agent; LangGraph owns transitions, adapters own I/O."""

    def __init__(self, max_iterations: int = 8, max_tool_calls: int = 32):
        if max_iterations < 1 or max_tool_calls < 1:
            raise ValueError("轮数和工具预算必须为正数")
        self.max_iterations = max_iterations
        self.max_tool_calls = max_tool_calls
        self.graph = build_graph(self._call_model, self._run_tool, TOOLS)

    @staticmethod
    async def _call_model(**kwargs):
        return await asyncio.wait_for(
            deepseek_client.chat.completions.create(**kwargs), timeout=60)

    @staticmethod
    async def _run_tool(name, arguments):
        return await asyncio.wait_for(execute_tool(name, arguments), timeout=12)

    async def run(self, user_message: str) -> dict:
        state = new_state(user_message, SYSTEM_PROMPT, settings.deepseek_model,
                          self.max_iterations, self.max_tool_calls)
        result = await self.graph.ainvoke(
            state, {"recursion_limit": 2 * self.max_iterations + 5})
        trace = result["trace"]
        await asyncio.to_thread(write_trace, trace, settings.trace_directory)
        return {
            "answer": result["answer"], "toolTrace": result["tool_trace"],
            "iterations": result["iteration"], "traceId": trace["traceId"],
            "status": result["status"], "trace": trace,
        }


ops_agent = OpsAgent()
