from types import SimpleNamespace

import pytest

from app.agent.ops_agent import OpsAgent
from app.agent.trace import safe_snapshot


def tool_call(
    name: str,
    arguments: str,
    call_id: str = "call-1",
):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(
            name=name,
            arguments=arguments,
        ),
    )


def llm_response(
    content: str | None,
    tool_calls: list | None = None,
):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=content,
                    tool_calls=tool_calls or [],
                )
            )
        ],
        usage=SimpleNamespace(
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
        ),
    )


class FakeCompletions:
    def __init__(self, responses):
        self.responses = list(responses)

    async def create(self, **kwargs):
        return self.responses.pop(0)


def fake_client(responses):
    return SimpleNamespace(
        chat=SimpleNamespace(
            completions=FakeCompletions(responses)
        )
    )


@pytest.mark.asyncio
async def test_trace_records_tool_and_redacts_sensitive_fields(
    monkeypatch,
):
    responses = [
        llm_response(
            "需要查询网元证据。",
            [tool_call("get_network_element", '{"ne_id": 7}')],
        ),
        llm_response("根因候选为网元7。"),
    ]

    async def fake_execute_tool(name, arguments):
        assert name == "get_network_element"
        assert arguments == {"ne_id": 7}
        return {
            "id": 7,
            "management_ip": "10.10.1.1",
            "serial_number": "SECRET-SERIAL",
        }

    monkeypatch.setattr(
        "app.agent.ops_agent.deepseek_client",
        fake_client(responses),
    )
    monkeypatch.setattr(
        "app.agent.ops_agent.execute_tool",
        fake_execute_tool,
    )

    result = await OpsAgent(max_iterations=3).run("诊断网元7")

    assert result["status"] == "COMPLETED"
    assert result["iterations"] == 2
    assert result["traceId"] == result["trace"]["traceId"]
    assert result["trace"]["metrics"]["toolCallCount"] == 1
    traced_result = result["trace"]["iterations"][0]["tools"][0]["result"]
    assert traced_result["management_ip"] == "***REDACTED***"
    assert traced_result["serial_number"] == "***REDACTED***"


@pytest.mark.asyncio
async def test_invalid_json_does_not_reuse_previous_arguments(monkeypatch):
    responses = [
        llm_response(
            "参数需要修正。",
            [tool_call("get_network_element", "{invalid-json")],
        ),
        llm_response("缺少有效工具参数，无法完成诊断。"),
    ]

    async def should_not_execute(*args, **kwargs):
        raise AssertionError("invalid JSON must not execute a tool")

    monkeypatch.setattr(
        "app.agent.ops_agent.deepseek_client",
        fake_client(responses),
    )
    monkeypatch.setattr(
        "app.agent.ops_agent.execute_tool",
        should_not_execute,
    )

    result = await OpsAgent(max_iterations=3).run("查询设备")

    first_call = result["toolTrace"][0]
    assert first_call["arguments"] == {}
    assert first_call["status"] == "FAILED"
    assert result["trace"]["metrics"]["toolErrorCount"] == 1


@pytest.mark.asyncio
async def test_max_iterations_is_explicit(monkeypatch):
    responses = [
        llm_response(
            "继续查询。",
            [tool_call("get_network_element", '{"ne_id": 7}')],
        )
    ]

    async def fake_execute_tool(name, arguments):
        return {"id": arguments["ne_id"]}

    monkeypatch.setattr(
        "app.agent.ops_agent.deepseek_client",
        fake_client(responses),
    )
    monkeypatch.setattr(
        "app.agent.ops_agent.execute_tool",
        fake_execute_tool,
    )

    result = await OpsAgent(max_iterations=1).run("继续诊断")

    assert result["status"] == "INCOMPLETE"
    assert result["trace"]["terminationReason"] == "MAX_ITERATIONS"


def test_safe_snapshot_bounds_large_results():
    snapshot = safe_snapshot({"payload": "x" * 20_000})

    assert snapshot["payload"].endswith("...<truncated>")
    assert len(snapshot["payload"]) < 2_100
