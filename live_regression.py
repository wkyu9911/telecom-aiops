"""Authorized seed-data regression. Reads local key without displaying it."""
import json
from pathlib import Path

import httpx

from app.core.config import settings


with httpx.Client(base_url='http://127.0.0.1:8000', timeout=180, trust_env=False) as client:
    before = client.get('http://127.0.0.1:8080/api/diagnoses', params={'size': 1}).json()['data']['total']
    headers = {'X-Agent-Key': settings.agent_api_key.get_secret_value()}
    first = client.post('/api/agent/sessions', headers=headers, json={
        'message': '请诊断网元9和10同时业务中断的共同根因，给出证据、替代解释和数据缺口。',
        'parameters': {'affected_ne_ids': [9, 10]}})
    first.raise_for_status()
    paused = first.json()
    assert paused['status'] == 'WAITING_INPUT'
    resumed = client.post(f"/api/agent/sessions/{paused['sessionId']}/resume", headers=headers,
        json={'parameters': {'start_time': '2026-08-27T17:50:00', 'end_time': '2026-08-27T18:10:00'}})
    resumed.raise_for_status()
    result = resumed.json()
    stored = client.get(f"/api/agent/traces/{result['traceId']}", headers=headers)
    stored.raise_for_status()
    assert stored.json()['traceId'] == result['traceId']
    after = client.get('http://127.0.0.1:8080/api/diagnoses', params={'size': 1}).json()['data']['total']
    assert before == after
    print(json.dumps({'initialStatus': paused['status'], 'finalStatus': result['status'],
        'iterations': result['iterations'], 'metrics': result['trace'].get('metrics'),
        'toolNames': [item['tool'] for item in result['toolTrace']],
        'traceStored': True, 'diagnosisRowsBefore': before, 'diagnosisRowsAfter': after,
        'answer': result['answer']}, ensure_ascii=False))
