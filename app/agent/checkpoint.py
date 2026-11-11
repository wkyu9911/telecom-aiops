"""Use the official Postgres saver with nonblocking thread bridges on Windows.

psycopg async connections require a selector loop on Windows. The synchronous
saver plus to_thread works with Uvicorn's default event loop as well.
"""
"""
保存图的执行状态和恢复所需信息，不是知识库，也不是单纯的操作日志。
"""
import asyncio
from contextlib import asynccontextmanager

import psycopg
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row


class ThreadedPostgresSaver(PostgresSaver):
    async def aget_tuple(self, config):
        return await asyncio.to_thread(self.get_tuple, config)

    async def aput(self, config, checkpoint, metadata, new_versions):
        return await asyncio.to_thread(self.put, config, checkpoint, metadata, new_versions)

    async def aput_writes(self, config, writes, task_id, task_path=''):
        return await asyncio.to_thread(self.put_writes, config, writes, task_id, task_path)

    async def alist(self, config, *, filter=None, before=None, limit=None):
        rows = await asyncio.to_thread(lambda: list(self.list(
            config, filter=filter, before=before, limit=limit)))
        for row in rows:
            yield row


@asynccontextmanager
async def checkpoint_saver(url: str):
    conn = await asyncio.to_thread(psycopg.connect, url, autocommit=True,
                                   prepare_threshold=0, row_factory=dict_row,
                                   connect_timeout=5)
    try:
        yield ThreadedPostgresSaver(conn)
    finally:
        await asyncio.to_thread(conn.close)
