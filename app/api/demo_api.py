import asyncio
import time
from typing import Any, Awaitable

from fastapi import APIRouter

from app.agent.trace import safe_snapshot
from app.tools.alarm_tools import get_alarm_window
from app.tools.anomaly_tools import get_anomalies_by_ne
from app.tools.diagnosis_tools import preview_diagnosis
from app.tools.kpi_tools import get_kpi_statistics
from app.tools.network_tools import get_network_element
from app.tools.topology_tools import find_common_upstream


router = APIRouter(
    prefix="/api/demo",
    tags=["Local Demo"],
)


DEMO_AFFECTED_NE_IDS = [9, 10]
DEMO_START_TIME = "2026-08-27T17:45:00"
DEMO_END_TIME = "2026-08-27T18:10:00"


async def _run_step(
    name: str,
    operation: Awaitable[Any],
) -> tuple[str, Any, dict[str, Any]]:
    started = time.perf_counter()

    try:
        result = await operation
    except Exception as exc:
        trace = {
            "name": name,
            "status": "FAILED",
            "latencyMs": int(
                (time.perf_counter() - started) * 1_000
            ),
            "errorType": type(exc).__name__,
            "error": str(exc),
        }
        raise RuntimeError(
            f"本地演示步骤失败: {name}: {exc}"
        ) from exc

    trace = {
        "name": name,
        "status": "SUCCESS",
        "latencyMs": int(
            (time.perf_counter() - started) * 1_000
        ),
        "result": safe_snapshot(result),
    }
    return name, result, trace


@router.get("/root-cause")
async def root_cause_demo():
    """Run a deterministic, read-only RCA demo without sending data to an LLM."""
    demo_started = time.perf_counter()
    trace: list[dict[str, Any]] = []

    _, common_upstream, step = await _run_step(
        "find_common_upstream",
        find_common_upstream(
            ne_ids=DEMO_AFFECTED_NE_IDS,
            max_depth=10,
        ),
    )
    trace.append(step)

    _, diagnosis, step = await _run_step(
        "preview_diagnosis",
        preview_diagnosis(
            affected_ne_ids=DEMO_AFFECTED_NE_IDS,
            start_time=DEMO_START_TIME,
            end_time=DEMO_END_TIME,
            max_depth=10,
        ),
    )
    trace.append(step)

    diagnosis_case = diagnosis.get("diagnosisCase", {})
    root_cause_ne_id = diagnosis_case.get("rootCauseNeId")

    if root_cause_ne_id is None:
        raise RuntimeError("诊断预览未返回 rootCauseNeId")

    evidence_operations = [
        _run_step(
            "get_root_cause_element",
            get_network_element(root_cause_ne_id),
        ),
        _run_step(
            "get_root_cause_alarms",
            get_alarm_window(
                root_cause_ne_id,
                DEMO_START_TIME,
                DEMO_END_TIME,
            ),
        ),
        _run_step(
            "get_root_cause_anomalies",
            get_anomalies_by_ne(root_cause_ne_id),
        ),
        _run_step(
            "get_root_cause_optical_power",
            get_kpi_statistics(
                ne_id=root_cause_ne_id,
                metric_code="OPTICAL_RX_POWER",
                start_time=DEMO_START_TIME,
                end_time=DEMO_END_TIME,
            ),
        ),
        _run_step(
            "get_gnb_01_throughput",
            get_kpi_statistics(
                ne_id=9,
                metric_code="DL_THROUGHPUT",
                start_time=DEMO_START_TIME,
                end_time=DEMO_END_TIME,
            ),
        ),
        _run_step(
            "get_gnb_02_throughput",
            get_kpi_statistics(
                ne_id=10,
                metric_code="DL_THROUGHPUT",
                start_time=DEMO_START_TIME,
                end_time=DEMO_END_TIME,
            ),
        ),
    ]
    evidence_results = await asyncio.gather(*evidence_operations)

    evidence: dict[str, Any] = {}
    for name, result, step in evidence_results:
        evidence[name] = result
        trace.append(step)

    root_element = safe_snapshot(
        evidence["get_root_cause_element"]
    )

    return {
        "mode": "LOCAL_DETERMINISTIC_READ_ONLY",
        "externalModelCalled": False,
        "scenario": {
            "affectedNeIds": DEMO_AFFECTED_NE_IDS,
            "startTime": DEMO_START_TIME,
            "endTime": DEMO_END_TIME,
            "symptom": "两个下游5G基站在同一窗口内传输中断",
        },
        "diagnosis": {
            "rootCause": {
                "neId": root_cause_ne_id,
                "neCode": root_element.get("neCode"),
                "neName": root_element.get("neName"),
            },
            "confidence": diagnosis_case.get("diagnosisConfidence"),
            "description": diagnosis_case.get(
                "rootCauseDescription"
            ),
            "method": diagnosis_case.get("diagnosisMethod"),
            "candidates": diagnosis.get("candidates", []),
        },
        "evidence": {
            "commonUpstream": safe_snapshot(common_upstream),
            "alarms": safe_snapshot(
                evidence["get_root_cause_alarms"]
            ),
            "anomalies": safe_snapshot(
                evidence["get_root_cause_anomalies"]
            ),
            "rootCauseOpticalPower": safe_snapshot(
                evidence["get_root_cause_optical_power"]
            ),
            "affectedThroughput": {
                "ne9": safe_snapshot(
                    evidence["get_gnb_01_throughput"]
                ),
                "ne10": safe_snapshot(
                    evidence["get_gnb_02_throughput"]
                ),
            },
        },
        "recommendations": [
            "优先检查汇聚交换机上联端口的光纤跳线、连接器和光模块。",
            "在授权维护窗口清洁并重新插拔连接器，然后复测光功率。",
            "恢复后确认链路稳定、告警清除及两个基站吞吐量回升。",
        ],
        "safety": {
            "databaseWrite": False,
            "sensitiveFieldsRedacted": True,
            "requiresHumanApprovalForRepair": True,
        },
        "trace": trace,
        "totalLatencyMs": int(
            (time.perf_counter() - demo_started) * 1_000
        ),
    }
