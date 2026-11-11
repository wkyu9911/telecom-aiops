from fastapi import APIRouter, Query

from app.tools.network_tools import get_network_element
from app.tools.topology_tools import (
    get_ancestors,
    find_common_upstream
)
from app.tools.kpi_tools import (
    get_kpi_statistics,
    compare_kpi_baseline
)
from app.tools.alarm_tools import get_alarm_window
from app.tools.anomaly_tools import get_anomalies_by_ne
from app.tools.diagnosis_tools import preview_diagnosis


router = APIRouter(
    prefix="/api/tools",
    tags=["Tools Debug"]
)


@router.get("/network-elements/{ne_id}")
async def network_element(
    ne_id: int
):
    return await get_network_element(ne_id)


@router.get("/topology/{ne_id}/ancestors")
async def ancestors(
    ne_id: int,
    max_depth: int = 10
):
    return await get_ancestors(
        ne_id,
        max_depth
    )


@router.get("/topology/common-upstream")
async def common_upstream(
    ne_ids: list[int] = Query(...),
    max_depth: int = 10
):
    return await find_common_upstream(
        ne_ids,
        max_depth
    )


@router.get("/kpi/statistics")
async def kpi_statistics(
    ne_id: int,
    metric_code: str,
    start_time: str,
    end_time: str
):
    return await get_kpi_statistics(
        ne_id,
        metric_code,
        start_time,
        end_time
    )


@router.get("/kpi/baseline-comparison")
async def kpi_baseline_comparison(
    ne_id: int,
    metric_code: str,
    baseline_start: str,
    baseline_end: str,
    current_start: str,
    current_end: str
):
    return await compare_kpi_baseline(
        ne_id,
        metric_code,
        baseline_start,
        baseline_end,
        current_start,
        current_end
    )


@router.get("/alarms/{ne_id}/window")
async def alarms_window(
    ne_id: int,
    start_time: str,
    end_time: str
):
    return await get_alarm_window(
        ne_id,
        start_time,
        end_time
    )


@router.get("/anomalies/{ne_id}")
async def anomalies(
    ne_id: int
):
    return await get_anomalies_by_ne(ne_id)


@router.post("/diagnosis/preview")
async def diagnosis_preview(
    affected_ne_ids: list[int],
    start_time: str,
    end_time: str,
    max_depth: int = 10
):
    return await preview_diagnosis(
        affected_ne_ids,
        start_time,
        end_time,
        max_depth
    )
