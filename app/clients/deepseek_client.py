from openai import AsyncOpenAI

from app.core.config import settings


class LazyDeepSeekClient:
    """Create the external client only when an Agent request needs it."""

    def __init__(self):
        self._client: AsyncOpenAI | None = None

    @property
    def chat(self):
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
            )
        return self._client.chat


deepseek_client = LazyDeepSeekClient()
