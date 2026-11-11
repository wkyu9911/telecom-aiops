"""One bounded JSON file per trace; local-only authorized diagnostic history."""
import json
import os
import tempfile
from pathlib import Path
from uuid import UUID

from app.agent.trace import safe_snapshot
"""
将 Trace 原子写入 JSON 文件，并提供按 Trace ID 读取功能
"""

def write_trace(trace: dict, directory: str = 'logs/traces'):
    trace_id = str(UUID(trace['traceId']))
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    # Trace entries were individually bounded and redacted when recorded.
    # Do not truncate the full trace and lose its structure.
    safe = dict(trace)
    safe['request'] = safe_snapshot(safe.get('request', {}))
    safe['finalAnswer'] = safe_snapshot(safe.get('finalAnswer'))
    fd, name = tempfile.mkstemp(prefix='.trace-', dir=root, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as output:
            json.dump(safe, output, ensure_ascii=False, default=str)
        os.replace(name, root / f'{trace_id}.json')
    finally:
        if os.path.exists(name):
            os.unlink(name)


def read_trace(trace_id: str, directory: str = 'logs/traces'):
    normalized = str(UUID(trace_id))
    return json.loads((Path(directory) / f'{normalized}.json').read_text(encoding='utf-8'))
