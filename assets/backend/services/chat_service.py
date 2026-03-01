# SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Chat business logic — create, get-or-create, clear-all.

Deduplicates chat creation logic previously scattered across
``routers/chats.py`` and ``routers/api_v1.py``.
"""

import uuid
from typing import Dict, List, Optional

from config import ConfigManager
from postgres_storage import PostgreSQLConversationStorage


async def create_chat(
    storage: PostgreSQLConversationStorage,
    config_manager: ConfigManager,
) -> Dict[str, str]:
    """Create a new chat, set metadata, and mark it as current.

    Returns dict with ``chat_id`` and ``message`` keys.
    """
    new_chat_id = str(uuid.uuid4())
    await storage.save_messages_immediate(new_chat_id, [])
    await storage.set_chat_metadata(new_chat_id, f"Chat {new_chat_id[:8]}")
    config_manager.updated_current_chat_id(new_chat_id)
    return {"chat_id": new_chat_id, "message": "New chat created"}


async def get_or_create_current_chat(
    storage: PostgreSQLConversationStorage,
    config_manager: ConfigManager,
) -> str:
    """Return the current chat ID, creating one if it doesn't exist."""
    cfg = config_manager.read_config()
    current_chat_id = cfg.current_chat_id

    if current_chat_id and await storage.exists(current_chat_id):
        return current_chat_id

    result = await create_chat(storage, config_manager)
    return result["chat_id"]


async def clear_all_chats(
    storage: PostgreSQLConversationStorage,
    config_manager: ConfigManager,
) -> Dict:
    """Delete all chats and create a fresh default chat.

    Returns dict with ``cleared_count``, ``new_chat_id``, ``message``.
    """
    chat_ids = await storage.list_conversations()
    cleared_count = 0
    for chat_id in chat_ids:
        if await storage.delete_conversation(chat_id):
            cleared_count += 1

    result = await create_chat(storage, config_manager)
    return {
        "cleared_count": cleared_count,
        "new_chat_id": result["chat_id"],
        "message": f"Cleared {cleared_count} chats and created new chat",
    }


async def list_chats(
    storage: PostgreSQLConversationStorage,
) -> List[str]:
    """Return all conversation IDs."""
    return await storage.list_conversations()


async def get_chat_messages(
    storage: PostgreSQLConversationStorage,
    chat_id: str,
    limit: Optional[int] = None,
) -> List[Dict]:
    """Return serialized messages for a chat."""
    messages = await storage.get_messages(chat_id, limit=limit)
    return [storage._message_to_dict(msg) for msg in messages]
