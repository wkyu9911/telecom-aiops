"""Local HTTP session/trace smoke; incomplete explicit input never invokes an LLM."""
import httpx

from app.core.config import settings


def main():
    headers = {'X-Agent-Key': settings.agent_api_key.get_secret_value()}
    with httpx.Client(base_url='http://127.0.0.1:8000', trust_env=False, timeout=15) as client:
        assert client.post('/api/agent/sessions', json={'message': 'test'}).status_code == 401
        response = client.post('/api/agent/sessions', headers=headers, json={
            'message': '诊断网元9和10，尚未提供时间',
            'parameters': {'affected_ne_ids': [9, 10]}})
        response.raise_for_status()
        result = response.json()
        assert result['status'] == 'WAITING_INPUT', result
        trace = client.get('/api/agent/traces/' + result['traceId'], headers=headers)
        trace.raise_for_status()
        print({'sessionStatus': result['status'], 'traceRead': trace.status_code,
               'unauthorized': 401, 'externalModel': False})


if __name__ == '__main__':
    main()
