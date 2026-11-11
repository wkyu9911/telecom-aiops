from typing import Any
from app.agent.validation import validate_arguments

from app.tools.network_tools import get_network_element
from app.tools.topology_tools import (
    get_ancestors,
    find_common_upstream
)
from app.tools.kpi_tools import get_kpi_statistics, list_kpi_metrics
from app.tools.alarm_tools import get_alarm_window
from app.tools.anomaly_tools import get_anomalies_by_ne, get_anomalies_in_window
from app.tools.diagnosis_tools import preview_diagnosis


async def execute_tool(
    name: str,
    arguments: dict
) -> Any:

    arguments = validate_arguments(name, arguments)

    if name == "list_kpi_metrics":
        return await list_kpi_metrics(**arguments)

    if name == "get_anomalies_in_window":
        return await get_anomalies_in_window(**arguments)

    if name == "get_network_element":
        return await get_network_element(
            ne_id=arguments["ne_id"]
        )

    if name == "get_ancestors":
        return await get_ancestors(
            ne_id=arguments["ne_id"],
            max_depth=arguments.get(
                "max_depth",
                10
            )
        )

    if name == "find_common_upstream":
        return await find_common_upstream(
            ne_ids=arguments["ne_ids"],
            max_depth=arguments.get(
                "max_depth",
                10
            )
        )

    if name == "get_kpi_statistics":
        return await get_kpi_statistics(
            ne_id=arguments["ne_id"],
            metric_code=arguments["metric_code"],
            start_time=arguments["start_time"],
            end_time=arguments["end_time"]
        )

    if name == "get_alarm_window":
        return await get_alarm_window(
            ne_id=arguments["ne_id"],
            start_time=arguments["start_time"],
            end_time=arguments["end_time"]
        )

    if name == "get_anomalies_by_ne":
        return await get_anomalies_by_ne(
            ne_id=arguments["ne_id"]
        )

    if name == "preview_diagnosis":
        return await preview_diagnosis(
            affected_ne_ids=arguments[
                "affected_ne_ids"
            ],
            start_time=arguments["start_time"],
            end_time=arguments["end_time"],
            max_depth=arguments.get(
                "max_depth",
                10
            )
        )

    raise ValueError(
        f"未知工具: {name}"
    )
