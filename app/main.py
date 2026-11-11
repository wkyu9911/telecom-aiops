from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.health_api import router as health_router
from app.api.tools_api import router as tools_router
from app.api.agent_api import router as agent_router
from app.api.demo_api import router as demo_router
from app.clients.springboot_client import SpringBootAPIError
from app.core.config import settings
from app.api.session_api import router as session_router


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI and Agent service for Telecom AIOps Platform"
)


app.include_router(health_router)
app.include_router(tools_router)
app.include_router(agent_router)
app.include_router(session_router)
app.include_router(demo_router)


@app.exception_handler(SpringBootAPIError)
async def spring_boot_api_error_handler(
    request: Request,
    exc: SpringBootAPIError
):
    return JSONResponse(
        status_code=502,
        content={
            "code": 502,
            "message": exc.message,
            "source": "spring-boot",
            "upstreamStatus": exc.status_code,
            "detail": exc.response_data
        }
    )


@app.get("/")
async def root():
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "springBootBaseUrl": (
            settings.spring_boot_base_url
        ),
        "llmProvider": "DeepSeek",
        "llmModel": settings.deepseek_model
    }
