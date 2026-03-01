# SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""FastAPI dependency injection providers.

All shared resources (config, storage, agent, vector store) are accessed
through these providers via ``Depends()``.  No router should ever
instantiate or import a global singleton directly.
"""

import os
from functools import lru_cache

from fastapi import Depends, Request

from config import ConfigManager
from postgres_storage import PostgreSQLConversationStorage


# ---------------------------------------------------------------------------
# Stateless singletons (safe to cache at module level)
# ---------------------------------------------------------------------------

@lru_cache()
def get_config_manager() -> ConfigManager:
    """Return the global ``ConfigManager`` singleton."""
    return ConfigManager("./config.json")


@lru_cache()
def get_postgres_storage() -> PostgreSQLConversationStorage:
    """Return the global ``PostgreSQLConversationStorage`` singleton."""
    return PostgreSQLConversationStorage(
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "chatbot"),
        user=os.getenv("POSTGRES_USER", "chatbot_user"),
        password=os.getenv("POSTGRES_PASSWORD", "chatbot_password"),
        cache_ttl=21600,  # 6 hours
    )


# ---------------------------------------------------------------------------
# Request-scoped providers (async-initialized, stored on app.state)
# ---------------------------------------------------------------------------

def get_agent(request: Request):
    """Return the ``ChatAgent`` attached during lifespan startup."""
    return request.app.state.agent


def get_vector_store(request: Request):
    """Return the ``VectorStore`` attached during lifespan startup."""
    return request.app.state.vector_store
