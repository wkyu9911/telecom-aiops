import asyncio
from app.agent.checkpoint import checkpoint_saver
from app.core.config import settings


async def main():
    if not settings.checkpoint_database_url:
        raise RuntimeError('Configure CHECKPOINT_DATABASE_URL first')
    async with checkpoint_saver(settings.checkpoint_database_url.get_secret_value()) as saver:
        await asyncio.to_thread(saver.setup)
    print('Official LangGraph checkpoint schema ready.')


if __name__ == '__main__':
    asyncio.run(main())
