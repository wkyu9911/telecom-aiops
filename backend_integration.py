"""Real graph, PostgreSQL, Java and MySQL; deterministic model fixture, no egress."""
import asyncio
import json
from types import SimpleNamespace

import httpx

from app.agent.ops_agent import OpsAgent
from app.agent.sessions import run_session


def response(content='', calls=()):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
        content=content, tool_calls=list(calls)))], usage=None)


def call(identifier, name, arguments):
    return SimpleNamespace(id=identifier, function=SimpleNamespace(
        name=name, arguments=json.dumps(arguments)))


async def model(**kwargs):
    results = [json.loads(m['content']) for m in kwargs['messages'] if m['role'] == 'tool']
    if not results:
        window = {'ne_id': 7, 'start_time': '2026-08-27T17:50:00', 'end_time': '2026-08-27T18:10:00'}
        return response(calls=[call('metrics', 'list_kpi_metrics', window),
            call('anomalies', 'get_anomalies_in_window', window),
            call('preview', 'preview_diagnosis', {'affected_ne_ids': [9, 10],
                'start_time': window['start_time'], 'end_time': window['end_time']})])
    assert 'OPTICAL_RX_POWER' in results[0]
    assert len(results[1]) == 3
    assert results[2]['diagnosisCase']['rootCauseNeId'] == 7
    return response('固定模型测试桩：实时证据与Java预览支持候选网元7，规则分0.775。')


async def main():
    OpsAgent._call_model = staticmethod(model)
    async with httpx.AsyncClient(trust_env=False) as client:
        before = (await client.get('http://127.0.0.1:8080/api/diagnoses', params={'size': 1})).json()['data']['total']
    paused = await run_session(message='诊断测试', parameters={'affected_ne_ids': [9, 10]})
    assert paused['status'] == 'WAITING_INPUT'
    result = await run_session(session_id=paused['sessionId'], resume=True,
        parameters={'start_time': '2026-08-27T17:50:00', 'end_time': '2026-08-27T18:10:00'})
    assert result['status'] == 'COMPLETED'
    assert result['trace']['metrics']['toolErrorCount'] == 0
    async with httpx.AsyncClient(trust_env=False) as client:
        after = (await client.get('http://127.0.0.1:8080/api/diagnoses', params={'size': 1})).json()['data']['total']
    assert before == after
    print(json.dumps({'status': result['status'], 'externalModel': False,
        'graph': result['trace']['nodes'], 'metrics': result['trace']['metrics'],
        'diagnosisRowsBefore': before, 'diagnosisRowsAfter': after}, ensure_ascii=False))


if __name__ == '__main__':
    asyncio.run(main())
