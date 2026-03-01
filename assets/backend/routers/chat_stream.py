# SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""SSE streaming endpoint for real-time chat completions.

Replaces WebSocket with a simpler HTTP-native pattern:
- POST /api/v1/chats/{chat_id}/completions  -> SSE token stream
- POST /api/v1/chats/{chat_id}/stop         -> cancel generation
"""

import asyncio
import json
import re
from typing import Dict, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from dependencies.providers import get_agent, get_postgres_storage
from errors import ErrorCode
from logger import logger

router = APIRouter(prefix="/api/v1", tags=["chat-stream"])

# Active generation streams — keyed by chat_id
_active_streams: Dict[str, asyncio.Event] = {}

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


# --------------- Request models ---------------

class ChatCompletionRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=32_000)
    image_id: Optional[str] = Field(
        None, min_length=1, max_length=128, pattern=r"^[0-9a-f-]+$"
    )


def _validate_chat_id(chat_id: str) -> Optional[JSONResponse]:
    """Return a JSONResponse if chat_id is invalid, else None."""
    if not _UUID_RE.match(chat_id):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": ErrorCode.VALIDATION_ERROR,
                    "message": "chat_id must be a valid UUID",
                    "details": {},
                }
            },
        )
    return None


# --------------- SSE generator ---------------

async def _sse_generator(
    agent, chat_id: str, message: str, image_data, stop_event: asyncio.Event
):
    """Yield SSE-formatted events from agent.query().

    Each line: ``data: <json>\\n\\n``
    Final line: ``data: [DONE]\\n\\n``
    """
    try:
        async for event in agent.query(
            query_text=message,
            chat_id=chat_id,
            image_data=image_data,
            stop_event=stop_event,
        ):
            if stop_event.is_set():
                yield f"data: {json.dumps({'type': 'stopped', 'message': 'Generation stopped'})}\n\n"
                return
            yield f"data: {json.dumps(event)}\n\n"
    except asyncio.CancelledError:
        logger.debug(f"SSE stream cancelled for chat {chat_id}")
        yield f"data: {json.dumps({'type': 'stopped', 'message': 'Generation cancelled'})}\n\n"
    except Exception as e:
        logger.error(f"SSE stream error for chat {chat_id}: {e}", exc_info=True)
        yield f"data: {json.dumps({'type': 'error', 'content': 'An internal error occurred'})}\n\n"
    finally:
        _active_streams.pop(chat_id, None)
        yield "data: [DONE]\n\n"


# --------------- Endpoints ---------------

@router.post("/chats/{chat_id}/completions")
async def chat_completion(
    chat_id: str,
    body: ChatCompletionRequest,
    request: Request,
    agent=Depends(get_agent),
    postgres_storage=Depends(get_postgres_storage),
):
    """Stream a chat completion as Server-Sent Events.

    The client sends a message and receives a stream of token events.
    Use ``POST /api/v1/chats/{chat_id}/stop`` to cancel mid-stream.
    """
    error_resp = _validate_chat_id(chat_id)
    if error_resp:
        return error_resp

    # Resolve optional image
    image_data = None
    if body.image_id:
        image_data = await postgres_storage.get_image(body.image_id)
        logger.debug(
            f"Retrieved image for {body.image_id}, "
            f"len={len(image_data) if image_data else 0}"
        )

    # Cancel any pre-existing stream for this chat_id
    existing = _active_streams.get(chat_id)
    if existing:
        existing.set()

    # Prepare stop event
    stop_event = asyncio.Event()
    _active_streams[chat_id] = stop_event

    # Monitor client disconnect → stop GPU work
    async def _disconnect_monitor():
        while not await request.is_disconnected():
            await asyncio.sleep(1)
        stop_event.set()
        logger.info(f"Client disconnected for chat {chat_id}, stopping generation")

    asyncio.create_task(_disconnect_monitor())

    logger.debug(f"SSE stream started for chat {chat_id}")

    return StreamingResponse(
        _sse_generator(agent, chat_id, body.message, image_data, stop_event),
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.post("/chats/{chat_id}/stop")
async def stop_generation(chat_id: str):
    """Signal the active stream for *chat_id* to stop generating."""
    error_resp = _validate_chat_id(chat_id)
    if error_resp:
        return error_resp

    event = _active_streams.get(chat_id)
    if event:
        event.set()
        logger.info(f"Stop signal sent for chat {chat_id}")
        return {"data": {"chat_id": chat_id, "status": "stopped"}}

    return {"data": {"chat_id": chat_id, "status": "no_active_stream"}}
