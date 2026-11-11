from app.clients.springboot_client import spring_boot_client


async def get_network_element(
    ne_id: int
) -> dict | None:

    return await spring_boot_client.get(
        f"/api/network-elements/{ne_id}"
    )


async def list_network_elements(
    page: int = 1,
    size: int = 20,
    ne_type: str | None = None,
    status: str | None = None
) -> dict:

    params = {
        "page": page,
        "size": size
    }

    if ne_type:
        params["neType"] = ne_type

    if status:
        params["status"] = status

    return await spring_boot_client.get(
        "/api/network-elements",
        params=params
    )
