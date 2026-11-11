from app.clients.springboot_client import spring_boot_client


async def get_upstream(
    ne_id: int
) -> list[dict]:

    return await spring_boot_client.get(
        f"/api/topology-relations/ne/{ne_id}/upstream"
    )


async def get_downstream(
    ne_id: int
) -> list[dict]:

    return await spring_boot_client.get(
        f"/api/topology-relations/ne/{ne_id}/downstream"
    )


async def get_neighbors(
    ne_id: int
) -> list[dict]:

    return await spring_boot_client.get(
        f"/api/topology-relations/ne/{ne_id}/neighbors"
    )


async def get_ancestors(
    ne_id: int,
    max_depth: int = 10
) -> list[dict]:

    return await spring_boot_client.get(
        f"/api/topology-relations/ne/{ne_id}/ancestors",
        params={
            "maxDepth": max_depth
        }
    )


async def find_common_upstream(
    ne_ids: list[int],
    max_depth: int = 10
) -> list[dict]:

    if len(ne_ids) < 2:
        raise ValueError(
            "find_common_upstream 至少需要两个设备ID"
        )

    return await spring_boot_client.get(
        "/api/topology-relations/common-upstream",
        params={
            "neIds": ne_ids,
            "maxDepth": max_depth
        }
    )
