"""Run create and resume in separate processes; real PostgreSQL, mocked model/tools."""
import asyncio
import json
import sys
from types import SimpleNamespace

from app.agent.ops_agent import OpsAgent
from app.agent.sessions import run_session


async def model(**kwargs):
    if 'response_format' in kwargs:
        raise AssertionError('Structured slots should not require extraction')
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
        content='模拟验证完成；未调用外部模型。', tool_calls=[]))], usage=None)


async def tool(name, arguments):
    return {'id': arguments['ne_id'], 'managementIp': 'sensitive-test-only'}


async def main():
    OpsAgent._call_model = staticmethod(model)
    OpsAgent._run_tool = staticmethod(tool)
    if sys.argv[1] == 'create':
        result = await run_session(message='诊断9和10', parameters={'affected_ne_ids': [9, 10]})
        assert result['status'] == 'WAITING_INPUT'
    else:
        result = await run_session(session_id=sys.argv[2], resume=True, parameters={
            'start_time': '2026-08-27T17:50:00', 'end_time': '2026-08-27T18:10:00'})
        assert result['status'] == 'COMPLETED'
        assert result['trace']['validation']['devices'][0]['managementIp'] == '***REDACTED***'
    print(json.dumps({'sessionId': result['sessionId'], 'status': result['status'],
                      'traceId': result['traceId'], 'externalModel': False}))


if __name__ == '__main__':
    asyncio.run(main())
