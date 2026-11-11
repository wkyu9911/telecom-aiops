from typing import Any

import httpx

from app.core.config import settings


class SpringBootAPIError(Exception):
    """Spring Boot API 调用异常。"""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_data: Any = None
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_data = response_data


class SpringBootClient:

    def __init__(self):
        self.base_url = settings.spring_boot_base_url.rstrip("/")
        self.timeout = httpx.Timeout(10.0)

    async def get(
        self,
        path: str,
        params: dict | None = None
    ) -> Any:

        return await self._request(
            method="GET",
            path=path,
            params=params
        )

    async def post(
        self,
        path: str,
        json: dict | None = None,
        params: dict | None = None
    ) -> Any:

        return await self._request(
            method="POST",
            path=path,
            params=params,
            json=json
        )

    async def put(
        self,
        path: str,
        json: dict | None = None
    ) -> Any:

        return await self._request(
            method="PUT",
            path=path,
            json=json
        )

    async def delete(
        self,
        path: str
    ) -> Any:

        return await self._request(
            method="DELETE",
            path=path
        )

    async def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        json: dict | None = None
    ) -> Any:

        url = f"{self.base_url}{path}"

        try:

            async with httpx.AsyncClient(
                timeout=self.timeout,
                # 仅用于本机测试
                trust_env=False
            ) as client:

                response = await client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json
                )

        except httpx.ConnectError as exc:

            raise SpringBootAPIError(
                message=(
                    f"无法连接 Spring Boot 服务: {url}。"
                    "请确认 Java 服务已经在 8080 端口启动。"
                )
            ) from exc

        except httpx.TimeoutException as exc:

            raise SpringBootAPIError(
                message=f"调用 Spring Boot 超时: {url}"
            ) from exc

        try:
            body = response.json()
        except ValueError:

            raise SpringBootAPIError(
                message="Spring Boot 返回了非 JSON 数据",
                status_code=response.status_code,
                response_data=response.text
            )

        if response.status_code < 200 or response.status_code >= 300:

            raise SpringBootAPIError(
                message=body.get(
                    "message",
                    f"HTTP {response.status_code}"
                ) if isinstance(body, dict)
                else f"HTTP {response.status_code}",
                status_code=response.status_code,
                response_data=body
            )

        # Java Result<T>:
        #
        # {
        #   "code": 200,
        #   "message": "success",
        #   "data": ...
        # }
        if isinstance(body, dict) and "code" in body:

            if body.get("code") != 200:

                raise SpringBootAPIError(
                    message=body.get(
                        "message",
                        "Spring Boot 业务调用失败"
                    ),
                    status_code=response.status_code,
                    response_data=body
                )

            return body.get("data")

        return body


spring_boot_client = SpringBootClient()
