from app.clients.springboot_client import spring_boot_client


async def get_active_alarms(
    ne_id: int
) -> list[dict]:

    return await spring_boot_client.get(
        f"/api/alarms/ne/{ne_id}/active"
    )


async def get_alarm_window(
    ne_id: int,
    start_time: str,
    end_time: str
) -> list[dict]:

    return await spring_boot_client.get(
        f"/api/alarms/ne/{ne_id}/window",
        params={
            "startTime": start_time,
            "endTime": end_time
        }
    )
