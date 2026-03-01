# SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""API endpoint tests for the refactored backend.

Uses synchronous TestClient with mocked DI providers (see conftest.py).
Covers health, chats, config/models, sources, RAG config, and error envelopes.
"""

from unittest.mock import AsyncMock, patch


# ── Health ──────────────────────────────────────────────────


def test_health(client):
    """GET /health returns status dict."""
    with patch(
        "services.health_service.check_all_services",
        new_callable=AsyncMock,
        return_value={"status": "ok", "services": {}},
    ):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


def test_health_rag(client):
    """GET /health/rag returns rag health (unhealthy OK in test env)."""
    resp = client.get("/health/rag")
    assert resp.status_code == 200
    assert "status" in resp.json()


# ── Chats ───────────────────────────────────────────────────


def test_list_chats_empty(client):
    """GET /api/v1/chats returns empty list when no chats exist."""
    resp = client.get("/api/v1/chats")
    assert resp.status_code == 200
    assert resp.json() == {"data": []}


def test_create_chat(client):
    """POST /api/v1/chats creates a new chat and returns its id."""
    resp = client.post("/api/v1/chats")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "chat_id" in data
    assert data["message"] == "New chat created"


def test_delete_chat_success(client):
    """DELETE /api/v1/chats/{id} succeeds when storage confirms deletion."""
    resp = client.delete("/api/v1/chats/test-id")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["chat_id"] == "test-id"


def test_delete_chat_not_found(client, mock_storage):
    """DELETE /api/v1/chats/{id} returns 404 when chat does not exist."""
    mock_storage.delete_conversation.return_value = False
    resp = client.delete("/api/v1/chats/nonexistent")
    assert resp.status_code == 404
    error = resp.json()["error"]
    assert error["code"] == "RESOURCE_NOT_FOUND"
    assert "nonexistent" in error["message"]


def test_get_chat_messages(client):
    """GET /api/v1/chats/{id}/messages returns messages list."""
    resp = client.get("/api/v1/chats/test-id/messages")
    assert resp.status_code == 200
    assert "data" in resp.json()


def test_clear_all_chats(client):
    """DELETE /api/v1/chats clears all conversations."""
    resp = client.delete("/api/v1/chats")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["deleted_count"] == 0  # mock list_conversations returns []


# ── Config / Models ─────────────────────────────────────────


def test_get_selected_model(client):
    """GET /api/v1/models/selected returns current model name."""
    resp = client.get("/api/v1/models/selected")
    assert resp.status_code == 200
    assert resp.json() == {"data": {"model": "gpt-oss-120b"}}


def test_get_available_models(client):
    """GET /api/v1/models/available lists all configured models."""
    resp = client.get("/api/v1/models/available")
    assert resp.status_code == 200
    assert resp.json() == {"data": {"models": ["gpt-oss-120b", "deepseek-coder"]}}


def test_set_selected_model(client):
    """POST /api/v1/models/selected updates the active model."""
    resp = client.post("/api/v1/models/selected", json={"model": "deepseek-coder"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["model"] == "deepseek-coder"
    assert data["message"] == "Selected model updated"


# ── Sources ─────────────────────────────────────────────────


def test_get_selected_sources(client):
    """GET /api/v1/selected-sources returns selected source list."""
    resp = client.get("/api/v1/selected-sources")
    assert resp.status_code == 200
    assert resp.json() == {"data": []}


def test_post_selected_sources(client):
    """POST /api/v1/selected-sources updates source selection."""
    resp = client.post("/api/v1/selected-sources", json={"sources": ["doc1.pdf"]})
    assert resp.status_code == 200
    assert resp.json() == {"data": {"selected_sources": ["doc1.pdf"]}}


# ── RAG Config ──────────────────────────────────────────────


def test_rag_config(client):
    """GET /api/v1/rag/config returns static feature availability info."""
    resp = client.get("/api/v1/rag/config")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "available"


# ── Error Envelopes ─────────────────────────────────────────


def test_error_400_validation(client):
    """Destructive admin op without ?confirm=true returns 400 VALIDATION_ERROR."""
    resp = client.delete("/api/v1/admin/collections")
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_error_envelope_structure(client, mock_storage):
    """Error responses always contain {error: {code, message}}."""
    mock_storage.delete_conversation.return_value = False
    resp = client.delete("/api/v1/chats/xyz")
    assert resp.status_code == 404
    body = resp.json()
    assert "error" in body
    error = body["error"]
    assert "code" in error
    assert "message" in error
