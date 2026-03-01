# SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for services.ingest_service.

Covers: queue_ingestion, get_task_status, _process_and_ingest_files.
All file I/O and external dependencies are mocked.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── queue_ingestion ────────────────────────────────────────


class TestQueueIngestion:
    """Tests for queue_ingestion."""

    def test_returns_task_id_and_queued_status(self):
        from services.ingest_service import queue_ingestion

        bg_tasks = MagicMock()
        file_info = [
            {"filename": "doc1.pdf", "content": b"pdf bytes"},
            {"filename": "doc2.txt", "content": b"text bytes"},
        ]
        vs = MagicMock()
        cm = MagicMock()

        result = queue_ingestion(file_info, vs, cm, bg_tasks)

        assert "task_id" in result
        assert result["status"] == "queued"
        assert result["files"] == ["doc1.pdf", "doc2.txt"]
        assert "2" in result["message"]
        bg_tasks.add_task.assert_called_once()

    def test_unique_task_ids(self):
        from services.ingest_service import queue_ingestion

        bg_tasks = MagicMock()
        file_info = [{"filename": "a.pdf", "content": b"data"}]
        vs = MagicMock()
        cm = MagicMock()

        r1 = queue_ingestion(file_info, vs, cm, bg_tasks)
        r2 = queue_ingestion(file_info, vs, cm, bg_tasks)

        assert r1["task_id"] != r2["task_id"]


# ── get_task_status ────────────────────────────────────────


class TestGetTaskStatus:
    """Tests for get_task_status."""

    def test_existing_task(self):
        from services.ingest_service import _indexing_tasks, get_task_status

        _indexing_tasks["test-id-123"] = "completed"
        assert get_task_status("test-id-123") == "completed"
        del _indexing_tasks["test-id-123"]

    def test_nonexistent_task(self):
        from services.ingest_service import get_task_status

        assert get_task_status("no-such-task") is None


# ── start_reindex_task ─────────────────────────────────────


class TestStartReindexTask:
    """Tests for start_reindex_task."""

    def test_creates_task_with_started_status(self):
        from services.ingest_service import _indexing_tasks, start_reindex_task

        task_id = start_reindex_task()
        assert task_id in _indexing_tasks
        assert _indexing_tasks[task_id] == "started"
        del _indexing_tasks[task_id]


# ── _process_and_ingest_files ──────────────────────────────


class TestProcessAndIngestFiles:
    """Tests for the background processing function."""

    @pytest.mark.asyncio
    @patch("services.ingest_service.os.makedirs")
    async def test_successful_ingestion(self, mock_makedirs):
        from services.ingest_service import _process_and_ingest_files

        vs = MagicMock()
        vs._load_documents.return_value = [MagicMock()]
        vs.index_documents = MagicMock()
        vs.register_source = MagicMock()

        cfg = MagicMock()
        cfg.sources = []
        cm = MagicMock()
        cm.read_config.return_value = cfg

        tasks = {}
        file_info = [{"filename": "test.pdf", "content": b"fake pdf"}]

        with patch("builtins.open", MagicMock()):
            await _process_and_ingest_files(file_info, vs, cm, "task-1", tasks)

        assert tasks["task-1"] == "completed"
        vs.index_documents.assert_called_once()
        cm.write_config.assert_called_once()

    @pytest.mark.asyncio
    @patch("services.ingest_service.os.makedirs")
    async def test_failed_indexing(self, mock_makedirs):
        from services.ingest_service import _process_and_ingest_files

        vs = MagicMock()
        vs._load_documents.side_effect = Exception("parse error")
        vs.register_source = MagicMock()

        cm = MagicMock()
        tasks = {}
        file_info = [{"filename": "bad.pdf", "content": b"corrupt"}]

        with patch("builtins.open", MagicMock()):
            await _process_and_ingest_files(file_info, vs, cm, "task-2", tasks)

        assert "failed" in tasks["task-2"]

    @pytest.mark.asyncio
    @patch("services.ingest_service.os.makedirs")
    async def test_status_transitions(self, mock_makedirs):
        """Verify task status progresses through expected stages."""
        from services.ingest_service import _process_and_ingest_files

        recorded_statuses = []

        class TrackingDict(dict):
            def __setitem__(self, key, value):
                recorded_statuses.append(value)
                super().__setitem__(key, value)

        vs = MagicMock()
        vs._load_documents.return_value = [MagicMock()]
        vs.index_documents = MagicMock()
        vs.register_source = MagicMock()

        cfg = MagicMock()
        cfg.sources = []
        cm = MagicMock()
        cm.read_config.return_value = cfg

        tasks = TrackingDict()
        file_info = [{"filename": "doc.pdf", "content": b"data"}]

        with patch("builtins.open", MagicMock()):
            await _process_and_ingest_files(file_info, vs, cm, "task-3", tasks)

        # Should transition: saving_files → loading_documents → indexing_documents → completed
        assert "saving_files" in recorded_statuses
        assert "loading_documents" in recorded_statuses
        assert "indexing_documents" in recorded_statuses
        assert "completed" in recorded_statuses


# ── API-level ingest test (via TestClient) ─────────────────


class TestIngestAPI:
    """Integration test for POST /api/v1/ingest via TestClient."""

    def test_ingest_endpoint(self, client):
        """POST /api/v1/ingest accepts file upload and returns task_id."""
        import io

        resp = client.post(
            "/api/v1/ingest",
            files=[
                ("files", ("test.txt", io.BytesIO(b"hello world"), "text/plain")),
            ],
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "task_id" in data
        assert data["status"] == "queued"
        assert "test.txt" in data["files"]

    def test_ingest_no_files(self, client):
        """POST /api/v1/ingest with no files returns queued task with empty file list."""
        resp = client.post("/api/v1/ingest")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "queued"
        assert data["files"] == []
