from app.clients.springboot_client import spring_boot_client


async def preview_diagnosis(
    affected_ne_ids: list[int],
    start_time: str,
    end_time: str,
    max_depth: int = 10
) -> dict:

    payload = {
        "affectedNeIds": affected_ne_ids,
        "startTime": start_time,
        "endTime": end_time,
        "maxDepth": max_depth
    }

    return await spring_boot_client.post(
        "/api/diagnoses/preview",
        json=payload
    )

"""该方法涉及到访问数据库，由此不直接将其放在Agent工具白名单"""
async def create_diagnosis(
    affected_ne_ids: list[int],
    start_time: str,
    end_time: str,
    max_depth: int = 10
) -> dict:

    payload = {
        "affectedNeIds": affected_ne_ids,
        "startTime": start_time,
        "endTime": end_time,
        "maxDepth": max_depth
    }

    return await spring_boot_client.post(
        "/api/diagnoses",
        json=payload
    )


async def get_diagnosis(
    diagnosis_id: int
) -> dict:

    return await spring_boot_client.get(
        f"/api/diagnoses/{diagnosis_id}"
    )
