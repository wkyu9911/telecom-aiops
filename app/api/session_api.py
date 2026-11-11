import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.agent.sessions import SessionBusyError, run_session
from app.agent.trace_store import read_trace
from app.core.config import settings


def authorize(x_agent_key: str = Header(default='')):
    expected = settings.agent_api_key
    if not expected:
        raise HTTPException(503, '诊断会话密钥尚未配置')
    if not secrets.compare_digest(x_agent_key, expected.get_secret_value()):
        raise HTTPException(401, '缺少有效诊断会话密钥')


router = APIRouter(prefix='/api/agent', tags=['Persistent Diagnosis'],
                   dependencies=[Depends(authorize)])


class SessionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    message: str = Field(min_length=1, max_length=8000)
    parameters: dict | None = None


class ResumeRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    parameters: dict


async def execute(**kwargs):
    try:
        return await run_session(**kwargs)
    except SessionBusyError:
        raise HTTPException(409, '会话正在执行，请勿重复恢复') from None
    except LookupError:
        raise HTTPException(404, '会话不存在') from None
    except ValueError:
        raise HTTPException(409, '会话状态不允许恢复') from None
    except Exception:
        raise HTTPException(503, '诊断会话执行失败，请检查Trace或数据库状态') from None


@router.post('/sessions')
async def create(request: SessionRequest):
    return await execute(message=request.message, parameters=request.parameters)


@router.post('/sessions/{session_id}/resume')
async def resume(session_id: UUID, request: ResumeRequest):
    return await execute(session_id=str(session_id), parameters=request.parameters, resume=True)


@router.get('/traces/{trace_id}')
async def trace(trace_id: UUID):
    import asyncio
    try:
        return await asyncio.to_thread(read_trace, str(trace_id), settings.trace_directory)
    except FileNotFoundError:
        raise HTTPException(404, 'Trace不存在') from None
