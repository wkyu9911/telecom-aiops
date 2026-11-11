from app.clients.springboot_client import spring_boot_client


async def get_anomalies_by_ne(
    ne_id: int
) -> list[dict]:

    return await spring_boot_client.get(
        f"/api/anomalies/ne/{ne_id}"
    )


async def detect_anomaly_preview(
    payload: dict
) -> dict:

    return await spring_boot_client.post(
        "/api/anomalies/detect-preview",
        json=payload
    )


async def detect_anomaly(
    payload: dict
) -> dict:

    return await spring_boot_client.post(
        "/api/anomalies/detect",
        json=payload
    )

async def get_anomalies_in_window(ne_id: int, start_time: str, end_time: str) -> list[dict]:
    return await spring_boot_client.get(f"/api/anomalies/ne/{ne_id}/window", params={
        "startTime": start_time, "endTime": end_time})
