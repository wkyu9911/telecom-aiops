from fastapi import APIRouter

router = APIRouter(
    prefix="/api/health",
    tags=["Health"]
)


@router.get("")
async def health():
    return {
        "status": "UP",
        "service": "telecom-aiops-ai-service"
    }
