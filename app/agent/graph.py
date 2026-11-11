"""Serializable LangGraph state; model and tools remain behind existing adapters."""
import copy
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from pydantic import ValidationError

from app.agent.trace import PROMPT_VERSION, safe_snapshot
from app.agent.validation import DiagnosisInput

"""
AgentState表示状态表单.
diagnosis利用不同值区分入口行为:
None	旧聊天入口，跳过专门的诊断参数提取与校验
{}	新诊断会话，没有直接提供结构化参数，需要尝试提取
"""
class AgentState(TypedDict, total=False):
    # 发送给模型的对话，包括历史对话、调用工具、工具结果。
    messages: list[dict]
    # 模型提出、等待执行的工具调用，从模型决策结果中提取出。
    pending_calls: list[dict]
    # 工具的调用记录
    tool_trace: list[dict]
    # 本次执行的可观察记录
    trace: dict
    # 当前执行了多少轮模型决策;
    # 计的是诊断模型决策节点的执行次数, 不等于所有 LLM 请求的总次数。
    iteration: int
    max_iterations: int
    max_tool_calls: int
    model: str
    status: str
    answer: str
    termination_reason: str | None
    started_epoch: float
    # 记录本次诊断中已经查询过的工具结果
    cache: dict[str, Any]
    # 设备ID、开始时间、结束时间等诊断参数，并不是真正的诊断实体。
    diagnosis: dict | None
    requires_confirmation: bool
    validation_call_count: int


def new_state(message: str, prompt: str, model: str, max_iterations: int,
              max_tool_calls: int = 32) -> AgentState:
    return {
        'messages': [{'role': 'system', 'content': prompt},
                     {'role': 'user', 'content': message}],
        'pending_calls': [], 'tool_trace': [], 'cache': {}, 'diagnosis': None,
        'requires_confirmation': False,
        'validation_call_count': 0,
        'iteration': 0, 'max_iterations': max_iterations,
        'max_tool_calls': max_tool_calls, 'model': model,
        'status': 'RUNNING', 'answer': '', 'termination_reason': None,
        'started_epoch': time.time(),
        'trace': {
            'traceId': str(uuid.uuid4()), 'status': 'RUNNING',
            'startedAt': datetime.now(timezone.utc).isoformat(),
            'finishedAt': None, 'request': {'message': safe_snapshot(message)},
            'configuration': {'model': model, 'promptVersion': PROMPT_VERSION,
                              'maxIterations': max_iterations,
                              'maxToolCalls': max_tool_calls, 'engine': 'langgraph'},
            'iterations': [], 'nodes': [],
        },
    }


def build_graph(call_model: Callable[..., Awaitable],
                run_tool: Callable[..., Awaitable], tools: list, checkpointer=None):
    """从自然语言中提取明确给出的设备和时间"""
    async def extract_node(state: AgentState):
        if state.get('diagnosis') is None:
            return {}
        trace = copy.deepcopy(state['trace'])
        trace['nodes'].append('extract_request')
        if state['diagnosis']:
            return {'trace': trace}
        started = time.perf_counter()
        try:
            response = await call_model(model=state['model'], stream=False,
                response_format={'type': 'json_object'}, messages=[{
                    'role': 'system', 'content': (
                    '只提取用户明确给出的诊断参数为JSON对象：affected_ne_ids整数数组、'
                    'start_time和end_time。未明确给出的字段设为null。不要猜补日期、'
                    '结束时间或设备。相对日期无法确定时设null。时间用ISO格式，'
                    '无时区按Asia/Shanghai解释。不要输出诊断结论。')},
                    state['messages'][-1]])
            data = json.loads(response.choices[0].message.content or '{}')
            if not isinstance(data, dict):
                raise ValueError('Expected object')
            data = {k: v for k, v in data.items()
                    if k in ('affected_ne_ids', 'start_time', 'end_time') and v is not None}
            trace['requestExtraction'] = {'status': 'SUCCESS',
                'latencyMs': int((time.perf_counter()-started)*1000),
                'parameters': safe_snapshot(data)}
            return {'diagnosis': data, 'trace': trace, 'requires_confirmation': True}
        except Exception as exc:
            trace['requestExtraction'] = {'status': 'FAILED', 'errorType': type(exc).__name__}
            # Ask the user for explicit slots instead of making up a window.
            return {'diagnosis': {}, 'trace': trace}

    """检查参数、必要时暂停、校验设备存在性"""
    async def validate_node(state: AgentState):
        if state.get('diagnosis') is None:
            return {}
        values = dict(state['diagnosis'])
        allowed_fields = {'affected_ne_ids', 'start_time', 'end_time'}
        if set(values) - allowed_fields:
            return {'status': 'FAILED', 'answer': '诊断参数包含未支持的字段。',
                    'termination_reason': 'INVALID_REQUEST_FIELDS'}
        confirmed = not state.get('requires_confirmation', False)
        while True:
            try:
                diagnosis = DiagnosisInput.model_validate(values).model_dump()
                if confirmed:
                    break
                prompt = {'status': 'WAITING_CONFIRMATION', 'parameters': diagnosis,
                          'message': '请核对模型提取的设备与时间；确认时提交 confirmed=true，可同时修正参数。'}
            except ValidationError as exc:
                issues = [{'field': '.'.join(str(x) for x in e['loc']),
                           'reason': e['msg']} for e in exc.errors()]
                prompt = {'status': 'WAITING_INPUT', 'issues': issues,
                    'required': ['affected_ne_ids', 'start_time', 'end_time'],
                    'parameters': safe_snapshot(values),
                    'message': '请补全或修正诊断设备与起止时间。无时区按Asia/Shanghai。'}
            patch = interrupt(prompt)
            if not isinstance(patch, dict):
                patch = {}
            confirmed = confirmed or patch.get('confirmed') is True
            values.update({k: v for k, v in patch.items()
                           if k in ('affected_ne_ids', 'start_time', 'end_time')})
        
        trace = copy.deepcopy(state['trace'])
        trace['nodes'].append('validate_request')
        cache = dict(state['cache'])
        devices = []
        validation_calls = 0
        try:
            # 通过ID查找设备信息，查到就放进设备队列并且记录tool调用
            # 主要目的是检验ID是否存在
            for ne_id in diagnosis['affected_ne_ids']:
                if validation_calls >= state['max_tool_calls']:
                    return {'trace': trace, 'status': 'INCOMPLETE',
                            'answer': '设备验证达到调用预算，诊断未完成。',
                            'validation_call_count': validation_calls,
                            'termination_reason': 'MAX_TOOL_CALLS'}
                validation_calls += 1
                data = safe_snapshot(await run_tool('get_network_element', {'ne_id': ne_id}))
                if not isinstance(data, dict) or data.get('id') != ne_id:
                    raise ValueError('设备不存在或返回格式错误')
                cache['get_network_element:' + json.dumps({'ne_id': ne_id}, sort_keys=True)] = data
                devices.append(data)
        except Exception as exc:
            trace['validation'] = {'status': 'FAILED', 'errorType': type(exc).__name__}
            return {'trace': trace, 'status': 'FAILED', 'answer': '设备验证失败，请核对设备ID或上游服务。',
                    'validation_call_count': validation_calls,
                    'termination_reason': 'DEVICE_VALIDATION_ERROR'}
        trace['validation'] = {'status': 'SUCCESS', 'parameters': safe_snapshot(diagnosis),
                               'devices': devices}
        policy = ('单设备诊断：先查本地证据与祖先路径，不调用多设备preview。'
                  if len(diagnosis['affected_ne_ids']) == 1 else
                  '多设备诊断：查询共同上游，结合告警、异常、KPI与preview。')
        messages = state['messages'] + [{'role': 'user', 'content':
            '已确认诊断参数：' + json.dumps(diagnosis, ensure_ascii=False) + '。' + policy}]
        return {'diagnosis': diagnosis, 'trace': trace, 'cache': cache, 'messages': messages,
                'validation_call_count': validation_calls, 'requires_confirmation': False}

    """调用模型，让它选择工具或给出回答"""
    async def model_node(state: AgentState):
        trace = copy.deepcopy(state['trace'])
        trace['nodes'].append('model')
        iteration = state['iteration'] + 1
        started = time.perf_counter()
        try:
            response = await call_model(model=state['model'],
                messages=state['messages'], tools=tools, tool_choice='auto', stream=False)
            message = response.choices[0].message
            calls = [{'id': c.id, 'type': 'function', 'function': {
                'name': c.function.name, 'arguments': c.function.arguments}}
                for c in (message.tool_calls or [])]
            content = message.content or ''
            usage = getattr(response, 'usage', None)
            entry = {'iteration': iteration, 'llm': {
                'model': state['model'], 'latencyMs': int((time.perf_counter()-started)*1000),
                'assistantSummary': safe_snapshot(content), 'toolCallCount': len(calls),
                'usage': {key: getattr(usage, attr, None) for key, attr in
                          [('promptTokens', 'prompt_tokens'),
                           ('completionTokens', 'completion_tokens'),
                           ('totalTokens', 'total_tokens')]}, 'error': None}, 'tools': []}
            trace['iterations'].append(entry)
        except Exception as exc:
            trace['iterations'].append({'iteration': iteration, 'llm': {
                'model': state['model'], 'latencyMs': int((time.perf_counter()-started)*1000),
                'assistantSummary': '', 'toolCallCount': 0, 'usage': {},
                'error': type(exc).__name__}, 'tools': []})
            return {'trace': trace, 'iteration': iteration, 'status': 'FAILED',
                    'pending_calls': [], 'termination_reason': 'LLM_ERROR',
                    'answer': f'模型服务调用失败，诊断未完成。错误类型：{type(exc).__name__}。'}
        assistant = {'role': 'assistant', 'content': content}
        if calls:
            assistant['tool_calls'] = calls
        update = {'trace': trace, 'iteration': iteration, 'pending_calls': calls,
                  'messages': state['messages'] + [assistant]}
        if not calls:
            update.update(status='COMPLETED', termination_reason='FINAL_ANSWER',
                          answer=content or '模型未返回文本结果')
        return update

    """执行工具、处理错误、缓存结果、记录过程"""
    async def tools_node(state: AgentState):
        trace = copy.deepcopy(state['trace'])
        trace['nodes'].append('tools')
        records = list(state['tool_trace'])
        messages = list(state['messages'])
        cache = dict(state['cache'])
        allowed = {tool['function']['name'] for tool in tools}
        exhausted = False
        for call in state['pending_calls']:
            name, arguments = call['function']['name'], {}
            status, error_type, cached = 'SUCCESS', None, False
            started = time.perf_counter()
            if len(records) + state.get('validation_call_count', 0) >= state['max_tool_calls']:
                exhausted = True
                break
            try:
                arguments = json.loads(call['function']['arguments'] or '{}')
                if not isinstance(arguments, dict):
                    raise ValueError('工具参数必须是JSON对象')
            except (json.JSONDecodeError, ValueError, TypeError):
                arguments = {}
                status, error_type = 'FAILED', 'INVALID_TOOL_ARGUMENTS'
                result = {'error': '模型生成了无效的JSON对象工具参数'}
            else:
                try:
                    if name not in allowed:
                        raise ValueError('未知或未授权工具')
                    key = name + ':' + json.dumps(arguments, sort_keys=True, ensure_ascii=False)
                    if key in cache:
                        cached, result = True, copy.deepcopy(cache[key])
                    else:
                        # Store only the bounded/redacted value used by the model.
                        result = safe_snapshot(await run_tool(name, arguments))
                        if not (isinstance(result, dict) and 'error' in result):
                            cache[key] = copy.deepcopy(result)
                except Exception as exc:
                    status, error_type = 'FAILED', type(exc).__name__
                    result = {'error': f'工具执行失败：{type(exc).__name__}'}
                    if isinstance(exc, ValidationError):
                        result['validationIssues'] = [
                            {'field': '.'.join(str(x) for x in e['loc']), 'reason': e['msg']}
                            for e in exc.errors(include_input=False, include_context=False)]
            latency = int((time.perf_counter()-started)*1000)
            record = {'iteration': state['iteration'], 'callId': call['id'],
                      'tool': name, 'arguments': safe_snapshot(arguments),
                      'result': safe_snapshot(result), 'status': status,
                      'latencyMs': latency, 'cacheHit': cached}
            records.append(record)
            trace['iterations'][-1]['tools'].append({
                'callId': call['id'], 'name': name, 'arguments': record['arguments'],
                'result': record['result'], 'status': status, 'latencyMs': latency,
                'errorType': error_type, 'cacheHit': cached})
            messages.append({'role': 'tool', 'tool_call_id': call['id'],
                'content': json.dumps(record['result'], ensure_ascii=False, default=str)})
        update = {'trace': trace, 'tool_trace': records, 'messages': messages,
                  'cache': cache, 'pending_calls': []}
        if exhausted or len(records) + state.get('validation_call_count', 0) >= state['max_tool_calls']:
            update.update(status='INCOMPLETE', termination_reason='MAX_TOOL_CALLS',
                          answer='Agent达到工具调用总数上限，诊断未完成。')
        elif state['iteration'] >= state['max_iterations']:
            update.update(status='INCOMPLETE', termination_reason='MAX_ITERATIONS',
                          answer='Agent达到最大工具调用轮数，未能完成最终结论。')
        return update

    """汇总状态、终止原因和统计信息"""
    def finalize(state: AgentState):
        trace = copy.deepcopy(state['trace'])
        trace['nodes'].append('finalize')
        trace.update(status=state['status'],
            finishedAt=datetime.now(timezone.utc).isoformat(),
            terminationReason=state['termination_reason'], finalAnswer=safe_snapshot(state['answer']))
        records = state['tool_trace']
        trace['metrics'] = {'iterationCount': state['iteration'], 'toolCallCount': len(records),
            'validationCallCount': state.get('validation_call_count', 0),
            'toolErrorCount': sum(r['status'] != 'SUCCESS' for r in records),
            'cacheHits': sum(r['cacheHit'] for r in records),
            'totalLatencyMs': int((time.time()-state['started_epoch'])*1000)}
        return {'trace': trace}

    graph = StateGraph(AgentState)
    graph.add_node('extract_request', extract_node)
    graph.add_node('validate_request', validate_node)
    graph.add_node('model', model_node)
    graph.add_node('tools', tools_node)
    graph.add_node('finalize', finalize)
    graph.add_edge(START, 'extract_request')
    graph.add_edge('extract_request', 'validate_request')
    graph.add_conditional_edges('validate_request',
        lambda s: 'model' if s['status'] == 'RUNNING' else 'finalize',
        {'model': 'model', 'finalize': 'finalize'})
    graph.add_conditional_edges('model',
        lambda s: 'tools' if s['status'] == 'RUNNING' else 'finalize',
        {'tools': 'tools', 'finalize': 'finalize'})
    graph.add_conditional_edges('tools',
        lambda s: 'model' if s['status'] == 'RUNNING' else 'finalize',
        {'model': 'model', 'finalize': 'finalize'})
    graph.add_edge('finalize', END)
    return graph.compile(checkpointer=checkpointer)
