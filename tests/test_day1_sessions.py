import json

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from pydantic import ValidationError

from app.agent.graph import build_graph, new_state
from app.agent.ops_agent import SYSTEM_PROMPT
from app.agent.tool_schemas import TOOLS
from app.agent.trace_store import read_trace, write_trace
from app.agent.validation import DiagnosisInput, validate_arguments
from tests.test_agent_trace import llm_response


@pytest.mark.parametrize('data', [
    {'affected_ne_ids': [9, 9], 'start_time': '2026-08-27T17:50:00', 'end_time': '2026-08-27T18:10:00'},
    {'affected_ne_ids': [-1], 'start_time': '2026-08-27T17:50:00', 'end_time': '2026-08-27T18:10:00'},
    {'affected_ne_ids': [9], 'start_time': '2026-08-27', 'end_time': '2026-08-28'},
    {'affected_ne_ids': [9], 'start_time': '2026-08-28T18:10:00', 'end_time': '2026-08-27T18:10:00'},
    {'affected_ne_ids': [9], 'start_time': '2026-08-01T18:10:00', 'end_time': '2026-08-27T18:10:00'},
])
def test_diagnosis_invalid_input(data):
    with pytest.raises(ValidationError):
        DiagnosisInput.model_validate(data)


def test_timezones_normalize_for_java():
    value = DiagnosisInput.model_validate({'affected_ne_ids': [9],
        'start_time': '2026-08-27T09:50:00Z', 'end_time': '2026-08-27T18:10:00+08:00'})
    assert value.start_time == '2026-08-27T17:50:00'


def test_preview_requires_distinct_multiple_devices():
    with pytest.raises(ValidationError):
        validate_arguments('preview_diagnosis', {'affected_ne_ids': [9, 9],
            'start_time': '2026-08-27T17:50:00', 'end_time': '2026-08-27T18:10:00'})


@pytest.mark.asyncio
async def test_pause_rebuild_graph_resume_and_prevent_guessing():
    memory = InMemorySaver()
    model_calls = []
    async def model(**kwargs):
        model_calls.append(kwargs)
        return llm_response('证据不足，不能确认根因')
    devices = []
    async def tool(name, arguments):
        devices.append(arguments['ne_id'])
        return {'id': arguments['ne_id']}
    state = new_state('诊断9和10', SYSTEM_PROMPT, 'test', 3)
    state['diagnosis'] = {'affected_ne_ids': [9, 10]}
    config = {'configurable': {'thread_id': 'pause-test'}}
    first = build_graph(model, tool, TOOLS, memory)
    result = await first.ainvoke(state, config)
    assert result['__interrupt__']
    assert not model_calls and not devices
    # Rebuild execution graph from the stored state, not Python local variables.
    second = build_graph(model, tool, TOOLS, memory)
    result = await second.ainvoke(Command(resume={
        'start_time': '2026-08-27T17:50:00', 'end_time': '2026-08-27T18:10:00'}), config)
    assert result['status'] == 'COMPLETED'
    assert devices == [9, 10]
    assert result['diagnosis']['start_time'] == '2026-08-27T17:50:00'


@pytest.mark.asyncio
async def test_failed_device_validation_stops_before_model():
    async def forbidden(**kwargs):
        pytest.fail('Model called with invalid device')
    async def missing(*args):
        return None
    state = new_state('诊断', SYSTEM_PROMPT, 'test', 3)
    state['diagnosis'] = {'affected_ne_ids': [999],
        'start_time': '2026-08-27T17:50:00', 'end_time': '2026-08-27T18:10:00'}
    result = await build_graph(forbidden, missing, TOOLS).ainvoke(state)
    assert result['termination_reason'] == 'DEVICE_VALIDATION_ERROR'


@pytest.mark.asyncio
async def test_extraction_does_not_invent_missing_time():
    async def model(**kwargs):
        assert 'response_format' in kwargs
        return llm_response(json.dumps({'affected_ne_ids': [9, 10],
                                       'start_time': None, 'end_time': None}))
    async def forbidden(*args):
        pytest.fail('Tools called before request complete')
    state = new_state('9和10故障了', SYSTEM_PROMPT, 'test', 3)
    state['diagnosis'] = {}
    result = await build_graph(model, forbidden, TOOLS, InMemorySaver()).ainvoke(
        state, {'configurable': {'thread_id': 'extraction'}})
    assert result['__interrupt__']
    assert 'start_time' not in result['diagnosis']


def test_session_and_trace_endpoints_require_key():
    from app.main import app
    with TestClient(app) as client:
        assert client.post('/api/agent/sessions', json={'message': '诊断'}).status_code in (401, 503)
        assert client.get('/api/agent/traces/00000000-0000-0000-0000-000000000001').status_code in (401, 503)


@pytest.mark.asyncio
async def test_complete_model_extraction_requires_user_confirmation():
    invoked = []
    async def model(**kwargs):
        if 'response_format' in kwargs:
            return llm_response(json.dumps({'affected_ne_ids': [9],
                'start_time': '2026-08-27T17:50:00', 'end_time': '2026-08-27T18:10:00'}))
        return llm_response('尚不能确定根因')
    async def tool(name, arguments):
        invoked.append(name)
        return {'id': arguments['ne_id']}
    graph = build_graph(model, tool, TOOLS, InMemorySaver())
    state = new_state('自然语言诊断', SYSTEM_PROMPT, 'test', 3)
    state['diagnosis'] = {}
    config = {'configurable': {'thread_id': 'confirmation'}}
    first = await graph.ainvoke(state, config)
    assert first['__interrupt__'][0].value['status'] == 'WAITING_CONFIRMATION'
    assert not invoked
    second = await graph.ainvoke(Command(resume={'confirmed': True}), config)
    assert second['status'] == 'COMPLETED'


def test_trace_file_roundtrip_and_no_path_traversal(tmp_path):
    trace = {'traceId': '00000000-0000-0000-0000-000000000001',
             'request': {'password': 'must-be-redacted'}, 'iterations': []}
    write_trace(trace, str(tmp_path))
    assert read_trace(trace['traceId'], str(tmp_path))['request']['password'] == '***REDACTED***'
    with pytest.raises(ValueError):
        read_trace('../outside', str(tmp_path))
