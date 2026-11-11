import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any
"""
提供脱敏、截断、Prompt 版本等公共能力；保留旧 AgentTrace 类。
注意，Trace 不等于模型隐藏思维链。
--------------------------------------
Trace 是一次任务的可观察执行记录，主要回答：
收到了什么请求？
使用什么配置？
经过哪些节点？
每轮模型返回了回答，还是提出了工具调用？
调用了哪个工具、传入什么参数、返回什么结果？
是否失败、是否命中缓存、耗时多少？
最后为什么结束？
"""

PROMPT_VERSION = "root-cause-v1"
MAX_TRACE_VALUE_CHARS = 2_000
MAX_TRACE_SNAPSHOT_CHARS = 8_000

SENSITIVE_KEY_PARTS = {
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "management_ip",
    "managementip",
    "password",
    "secret",
    "serial_number",
    "serialnumber",
    "token",
}


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)


def _redact(value: Any, key: str = "") -> Any:
    if key and _is_sensitive_key(key):
        return "***REDACTED***"

    if isinstance(value, dict):
        return {
            str(item_key): _redact(item_value, str(item_key))
            for item_key, item_value in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value]

    if isinstance(value, str) and len(value) > MAX_TRACE_VALUE_CHARS:
        return value[:MAX_TRACE_VALUE_CHARS] + "...<truncated>"

    return value


def safe_snapshot(value: Any) -> Any:
    """Return a bounded, redacted representation suitable for trace output."""
    redacted = _redact(value)

    try:
        serialized = json.dumps(
            redacted,
            ensure_ascii=False,
            default=str,
        )
    except (TypeError, ValueError):
        serialized = str(redacted)

    if len(serialized) <= MAX_TRACE_SNAPSHOT_CHARS:
        return redacted

    return {
        "truncated": True,
        "preview": serialized[:MAX_TRACE_SNAPSHOT_CHARS],
        "originalChars": len(serialized),
    }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AgentTrace:
    """Collect observable Agent decisions without storing hidden reasoning."""

    def __init__(
        self,
        user_message: str,
        model: str,
        max_iterations: int,
    ):
        self.trace_id = str(uuid.uuid4())
        self.started_at = utc_now_iso()
        self._started_perf = time.perf_counter()
        self.user_message = safe_snapshot(user_message)
        self.model = model
        self.max_iterations = max_iterations
        self.iterations: list[dict[str, Any]] = []
        self.status = "RUNNING"
        self.termination_reason: str | None = None
        self.final_answer: str | None = None
        self.finished_at: str | None = None

    def add_iteration(
        self,
        iteration: int,
        latency_ms: int,
        assistant_summary: str | None,
        tool_call_count: int,
        usage: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        entry = {
            "iteration": iteration,
            "llm": {
                "model": self.model,
                "latencyMs": latency_ms,
                "assistantSummary": safe_snapshot(
                    assistant_summary or ""
                ),
                "toolCallCount": tool_call_count,
                "usage": safe_snapshot(usage or {}),
                "error": safe_snapshot(error) if error else None,
            },
            "tools": [],
        }
        self.iterations.append(entry)
        return entry

    def add_tool(
        self,
        iteration_entry: dict[str, Any],
        call_id: str,
        name: str,
        arguments: dict[str, Any],
        result: Any,
        status: str,
        latency_ms: int,
        error_type: str | None = None,
    ) -> None:
        iteration_entry["tools"].append(
            {
                "callId": call_id,
                "name": name,
                "arguments": safe_snapshot(arguments),
                "result": safe_snapshot(result),
                "status": status,
                "latencyMs": latency_ms,
                "errorType": error_type,
            }
        )

    def finish(
        self,
        status: str,
        termination_reason: str,
        final_answer: str,
    ) -> dict[str, Any]:
        self.status = status
        self.termination_reason = termination_reason
        self.final_answer = final_answer
        self.finished_at = utc_now_iso()
        return self.as_dict()

    def as_dict(self) -> dict[str, Any]:
        tool_calls = sum(
            len(item["tools"])
            for item in self.iterations
        )
        tool_errors = sum(
            1
            for item in self.iterations
            for tool in item["tools"]
            if tool["status"] != "SUCCESS"
        )

        return {
            "traceId": self.trace_id,
            "status": self.status,
            "startedAt": self.started_at,
            "finishedAt": self.finished_at,
            "request": {
                "message": self.user_message,
            },
            "configuration": {
                "model": self.model,
                "promptVersion": PROMPT_VERSION,
                "maxIterations": self.max_iterations,
            },
            "iterations": self.iterations,
            "terminationReason": self.termination_reason,
            "finalAnswer": safe_snapshot(self.final_answer),
            "metrics": {
                "iterationCount": len(self.iterations),
                "toolCallCount": tool_calls,
                "toolErrorCount": tool_errors,
                "totalLatencyMs": int(
                    (time.perf_counter() - self._started_perf) * 1_000
                ),
            },
        }
