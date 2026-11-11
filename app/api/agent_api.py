from fastapi import APIRouter

from app.agent.ops_agent import ops_agent
from app.models.schemas import (
    AgentChatRequest,
    AgentChatResponse
)


router = APIRouter(
    prefix="/api/agent",
    tags=["AIOps Agent"]
)


@router.post(
    "/chat",
    response_model=AgentChatResponse
)
async def chat(
    request: AgentChatRequest
):

    return await ops_agent.run(
        request.message
    )
