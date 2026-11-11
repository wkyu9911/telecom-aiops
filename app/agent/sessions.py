"""Persistent local diagnostic sessions; no in-memory fallback on DB failure."""
import asyncio
import copy
from uuid import UUID, uuid4

from langgraph.types import Command

from app.agent.checkpoint import checkpoint_saver
from app.agent.graph import build_graph, new_state
from app.agent.ops_agent import OpsAgent, SYSTEM_PROMPT
from app.agent.tool_schemas import TOOLS
from app.agent.trace_store import write_trace
from app.core.config import settings

"""
管理一次任务如何启动、暂停和继续
比如用户提交：分析网元 9 和 10 的共同故障。
缺少时间时，任务不必失败，也不应猜时间，而是暂停。待用户补充时间后，用同一个会话 ID 继续执行。
"""
class SessionBusyError(Exception):
    pass


async def run_session(message: str = '', parameters: dict | None = None,
                      session_id: str | None = None, resume: bool = False):
    if not settings.checkpoint_database_url:
        raise RuntimeError('Checkpoint database not configured')
    identifier = str(UUID(session_id)) if session_id else str(uuid4())
    async with checkpoint_saver(settings.checkpoint_database_url.get_secret_value()) as saver:
        # Cross-process lock prevents two concurrent resumes of the same task.
        locked = await asyncio.to_thread(lambda: saver.conn.execute(
            'SELECT pg_try_advisory_lock(hashtextextended(%s, 0)) AS locked',
            (identifier,)).fetchone()['locked'])
        if not locked:
            raise SessionBusyError('会话正在执行')
        graph = build_graph(OpsAgent._call_model, OpsAgent._run_tool, TOOLS, saver)
        config = {'configurable': {'thread_id': identifier}, 'recursion_limit': 25}
        if resume:
            snapshot = await graph.aget_state(config)
            if not snapshot.values:
                raise LookupError('会话不存在')
            if not snapshot.next:
                raise ValueError('会话已结束，不能再次恢复')
            value = Command(resume=parameters or {})
        else:
            value = new_state(message, SYSTEM_PROMPT, settings.deepseek_model, 8, 32)
            value['diagnosis'] = parameters or {}
        result = await graph.ainvoke(value, config)
        trace = copy.deepcopy(result['trace'])
        pending = result.get('__interrupt__', ())
        if pending:
            status = pending[0].value.get('status', 'WAITING_INPUT')
            trace['status'] = status
            trace['terminationReason'] = 'NEEDS_CONFIRMATION' if status == 'WAITING_CONFIRMATION' else 'NEEDS_INPUT'
        else:
            status = result['status']
        trace['sessionId'] = identifier
        await asyncio.to_thread(write_trace, trace, settings.trace_directory)
        return {'sessionId': identifier, 'status': status,
                'answer': result.get('answer', ''),
                'clarifications': [item.value for item in pending],
                'traceId': trace['traceId'], 'trace': trace,
                'iterations': result['iteration'], 'toolTrace': result['tool_trace']}
