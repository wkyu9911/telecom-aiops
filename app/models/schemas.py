from pydantic import BaseModel, Field


class AgentChatRequest(BaseModel):

    message: str = Field(
        ...,
        min_length=1,
        description="发送给AIOps智能体的自然语言问题"
    )


class AgentChatResponse(BaseModel):

    answer: str
    toolTrace: list
    iterations: int
    traceId: str
    status: str
    trace: dict
