import asyncio
import json
from types import SimpleNamespace

import pytest

from app.agent.ops_agent import OpsAgent
from tests.test_agent_trace import fake_client, llm_response, tool_call


@pytest.mark.asyncio
async def test_no_tool_finishes_in_graph(monkeypatch):
    monkeypatch.setattr('app.agent.ops_agent.deepseek_client', fake_client([llm_response('你好')]))
    result = await OpsAgent().run('你是谁')
    assert result['answer'] == '你好'
    assert result['trace']['nodes'] == ['model', 'finalize']
    assert result['toolTrace'] == []


@pytest.mark.asyncio
async def test_llm_failure_has_terminal_trace(monkeypatch):
    async def fail(**kwargs):
        raise TimeoutError('sensitive upstream body must not be logged')
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=fail)))
    monkeypatch.setattr('app.agent.ops_agent.deepseek_client', client)
    result = await OpsAgent().run('故障分析')
    assert result['status'] == 'FAILED'
    assert result['trace']['terminationReason'] == 'LLM_ERROR'
    assert 'sensitive upstream' not in json.dumps(result)


@pytest.mark.asyncio
@pytest.mark.parametrize('arguments', ['[]', 'null', '7', '"text"'])
async def test_non_object_tool_arguments_rejected(monkeypatch, arguments):
    monkeypatch.setattr('app.agent.ops_agent.deepseek_client', fake_client([
        llm_response(None, [tool_call('get_network_element', arguments)]), llm_response('缺参数')]))
    async def forbidden(*args):
        pytest.fail('Invalid arguments executed')
    monkeypatch.setattr('app.agent.ops_agent.execute_tool', forbidden)
    result = await OpsAgent().run('查询')
    assert result['toolTrace'][0]['arguments'] == {}
    assert result['toolTrace'][0]['status'] == 'FAILED'


@pytest.mark.asyncio
async def test_cache_is_per_request_and_model_input_redacted(monkeypatch):
    calls = []
    invocations = []
    responses = [llm_response(None, [tool_call('get_network_element', '{"ne_id":7}', 'a')]),
                 llm_response(None, [tool_call('get_network_element', '{"ne_id":7}', 'b')]),
                 llm_response('完成')]
    async def complete(**kwargs):
        invocations.append(kwargs)
        return responses.pop(0)
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=complete)))
    monkeypatch.setattr('app.agent.ops_agent.deepseek_client', client)
    async def tool(name, arguments):
        calls.append(name)
        return {'id': 7, 'managementIp': 'sensitive-ip'}
    monkeypatch.setattr('app.agent.ops_agent.execute_tool', tool)
    result = await OpsAgent().run('查询7')
    assert len(calls) == 1
    assert result['trace']['metrics']['cacheHits'] == 1
    assert 'sensitive-ip' not in json.dumps(invocations[-1])
    assert result['trace']['nodes'] == ['model', 'tools', 'model', 'tools', 'model', 'finalize']


@pytest.mark.asyncio
async def test_batch_tool_budget_prevents_extra_execution(monkeypatch):
    monkeypatch.setattr('app.agent.ops_agent.deepseek_client', fake_client([
        llm_response(None, [tool_call('get_network_element', '{"ne_id":7}', 'a'),
                            tool_call('get_network_element', '{"ne_id":8}', 'b')])]))
    called = []
    async def tool(name, arguments):
        called.append(arguments['ne_id'])
        return {'id': arguments['ne_id']}
    monkeypatch.setattr('app.agent.ops_agent.execute_tool', tool)
    result = await OpsAgent(max_tool_calls=1).run('查询')
    assert called == [7]
    assert result['trace']['terminationReason'] == 'MAX_TOOL_CALLS'


@pytest.mark.asyncio
async def test_unknown_tool_is_not_executed(monkeypatch):
    monkeypatch.setattr('app.agent.ops_agent.deepseek_client', fake_client([
        llm_response(None, [tool_call('delete_database', '{}')]), llm_response('拒绝')]))
    async def forbidden(*args):
        pytest.fail('Unauthorized tool executed')
    monkeypatch.setattr('app.agent.ops_agent.execute_tool', forbidden)
    result = await OpsAgent().run('查询')
    assert result['toolTrace'][0]['status'] == 'FAILED'


@pytest.mark.asyncio
async def test_tool_failure_can_be_followed_by_final_answer(monkeypatch):
    monkeypatch.setattr('app.agent.ops_agent.deepseek_client', fake_client([
        llm_response(None, [tool_call('get_network_element', '{"ne_id":7}')]),
        llm_response('上游不可用，证据不足')]))
    async def fail(*args):
        raise TimeoutError('secret detail')
    monkeypatch.setattr('app.agent.ops_agent.execute_tool', fail)
    result = await OpsAgent().run('查询')
    assert result['status'] == 'COMPLETED'
    assert result['trace']['metrics']['toolErrorCount'] == 1
    assert 'secret detail' not in json.dumps(result)
