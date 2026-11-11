from app.clients.springboot_client import spring_boot_client


async def get_kpi_timeseries(
    ne_id: int,
    metric_code: str,
    start_time: str,
    end_time: str
) -> list[dict]:

    return await spring_boot_client.get(
        "/api/kpis/timeseries",
        params={
            "neId": ne_id,
            "metricCode": metric_code,
            "startTime": start_time,
            "endTime": end_time
        }
    )


async def get_latest_kpi(
    ne_id: int,
    metric_code: str
) -> dict:

    return await spring_boot_client.get(
        "/api/kpis/latest",
        params={
            "neId": ne_id,
            "metricCode": metric_code
        }
    )


async def get_kpi_statistics(
    ne_id: int,
    metric_code: str,
    start_time: str,
    end_time: str
) -> dict:

    return await spring_boot_client.get(
        "/api/kpis/statistics",
        params={
            "neId": ne_id,
            "metricCode": metric_code,
            "startTime": start_time,
            "endTime": end_time
        }
    )


async def compare_kpi_baseline(
    ne_id: int,
    metric_code: str,
    baseline_start: str,
    baseline_end: str,
    current_start: str,
    current_end: str
) -> dict:

    return await spring_boot_client.get(
        "/api/kpis/baseline-comparison",
        params={
            "neId": ne_id,
            "metricCode": metric_code,
            "baselineStart": baseline_start,
            "baselineEnd": baseline_end,
            "currentStart": current_start,
            "currentEnd": current_end
        }
    )

async def list_kpi_metrics(ne_id: int, start_time: str, end_time: str) -> list[str]:
    return await spring_boot_client.get("/api/kpis/metrics", params={
        "neId": ne_id, "startTime": start_time, "endTime": end_time})
