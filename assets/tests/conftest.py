# SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Shared test fixtures — synchronous TestClient with mocked DI providers."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from main import app
from dependencies.providers import (
    get_config_manager,
    get_postgres_storage,
    get_agent,
    get_vector_store,
)


# ── Mock factories ───────────────────────────────────────────


@pytest.fixture()
def mock_config():
    """Mock ConfigManager (sync methods)."""
    cm = MagicMock()
    cm.get_selected_model.return_value = "gpt-oss-120b"
    cm.get_available_models.return_value = ["gpt-oss-120b", "deepseek-coder"]

    cfg = MagicMock()
    cfg.selected_model = "gpt-oss-120b"
    cfg.selected_sources = []
    cfg.models = ["gpt-oss-120b", "deepseek-coder"]
    cm.read_config.return_value = cfg

    cm.update_selected_model.return_value = None
    cm.update_selected_sources.return_value = None
    return cm


@pytest.fixture()
def mock_storage():
    """Mock PostgreSQLConversationStorage (async methods)."""
    s = AsyncMock()
    s.list_conversations.return_value = []
    s.create_conversation.return_value = "test-chat-id"
    s.delete_conversation.return_value = True
    s.get_messages.return_value = []
    s.get_chat_metadata.return_value = {"title": "Test Chat"}
    s.check_connection.return_value = True
    s.clear_all_conversations.return_value = None
    s.rename_conversation.return_value = None
    s.update_chat_metadata.return_value = None
    return s


@pytest.fixture()
def mock_agent():
    """Mock ChatAgent."""
    return AsyncMock()


@pytest.fixture()
def mock_vs():
    """Mock VectorStore (sync methods)."""
    vs = MagicMock()
    vs.get_sources.return_value = ["doc1.pdf", "doc2.pdf"]
    vs.get_all_sources.return_value = ["doc1.pdf", "doc2.pdf"]
    vs.get_documents.return_value = []
    vs.get_documents_with_scores.return_value = ([], [])
    return vs


# ── TestClient ───────────────────────────────────────────────


@pytest.fixture()
def client(mock_config, mock_storage, mock_agent, mock_vs):
    """Synchronous TestClient with all external deps mocked."""

    @asynccontextmanager
    async def _test_lifespan(a):
        a.state.agent = mock_agent
        a.state.vector_store = mock_vs
        yield

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = _test_lifespan

    app.dependency_overrides[get_config_manager] = lambda: mock_config
    app.dependency_overrides[get_postgres_storage] = lambda: mock_storage
    app.dependency_overrides[get_agent] = lambda: mock_agent
    app.dependency_overrides[get_vector_store] = lambda: mock_vs

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
    app.router.lifespan_context = original_lifespan
