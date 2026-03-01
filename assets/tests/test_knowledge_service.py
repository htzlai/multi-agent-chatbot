# SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for services.knowledge_service.

Covers 3-layer reconciliation (config, files, vectors), sync, and delete.
All external dependencies (Milvus, filesystem) are mocked.
"""

import json
import os
import pytest
from unittest.mock import MagicMock, patch, mock_open


# ── Knowledge Status ───────────────────────────────────────


class TestGetKnowledgeStatus:
    """Tests for get_knowledge_status (3-layer reconciliation)."""

    def _make_config(self, sources, selected_sources=None):
        cfg = MagicMock()
        cfg.sources = list(sources)
        cfg.selected_sources = list(selected_sources or [])
        return cfg

    def _make_config_manager(self, sources, selected_sources=None):
        cm = MagicMock()
        cm.read_config.return_value = self._make_config(sources, selected_sources)
        return cm

    @patch("services.knowledge_service.milvus_vector_counts")
    @patch("services.knowledge_service.query_unique_sources")
    @patch("services.knowledge_service._read_source_mapping")
    def test_fully_synced(self, mock_mapping, mock_vectors, mock_counts):
        """All three layers agree — no issues."""
        from services.knowledge_service import get_knowledge_status

        mock_mapping.return_value = {"doc1.pdf": "task-1", "doc2.pdf": "task-2"}
        mock_vectors.return_value = {"doc1.pdf", "doc2.pdf"}
        mock_counts.return_value = {"count": 100}

        cm = self._make_config_manager(["doc1.pdf", "doc2.pdf"])
        result = get_knowledge_status(cm)

        assert result["status"] == "ok"
        assert result["summary"]["config_files_match"] is True
        assert result["summary"]["files_indexed"] is True
        assert result["summary"]["vectors_clean"] is True
        assert result["summary"]["fully_synced_count"] == 2

    @patch("services.knowledge_service.milvus_vector_counts")
    @patch("services.knowledge_service.query_unique_sources")
    @patch("services.knowledge_service._read_source_mapping")
    def test_orphaned_in_config(self, mock_mapping, mock_vectors, mock_counts):
        """Config has source that has no file on disk."""
        from services.knowledge_service import get_knowledge_status

        mock_mapping.return_value = {"doc1.pdf": "task-1"}  # no doc2
        mock_vectors.return_value = {"doc1.pdf"}
        mock_counts.return_value = {"count": 50}

        cm = self._make_config_manager(["doc1.pdf", "doc2.pdf"])
        result = get_knowledge_status(cm)

        assert "doc2.pdf" in result["issues"]["orphaned_in_config"]
        assert result["summary"]["config_files_match"] is False

    @patch("services.knowledge_service.milvus_vector_counts")
    @patch("services.knowledge_service.query_unique_sources")
    @patch("services.knowledge_service._read_source_mapping")
    def test_untracked_files(self, mock_mapping, mock_vectors, mock_counts):
        """File exists on disk but not in config."""
        from services.knowledge_service import get_knowledge_status

        mock_mapping.return_value = {"doc1.pdf": "t1", "extra.pdf": "t2"}
        mock_vectors.return_value = {"doc1.pdf"}
        mock_counts.return_value = {"count": 50}

        cm = self._make_config_manager(["doc1.pdf"])
        result = get_knowledge_status(cm)

        assert "extra.pdf" in result["issues"]["untracked_files"]

    @patch("services.knowledge_service.milvus_vector_counts")
    @patch("services.knowledge_service.query_unique_sources")
    @patch("services.knowledge_service._read_source_mapping")
    def test_need_indexing(self, mock_mapping, mock_vectors, mock_counts):
        """File exists but has no vectors yet."""
        from services.knowledge_service import get_knowledge_status

        mock_mapping.return_value = {"doc1.pdf": "t1", "new.pdf": "t2"}
        mock_vectors.return_value = {"doc1.pdf"}  # new.pdf not yet indexed
        mock_counts.return_value = {"count": 50}

        cm = self._make_config_manager(["doc1.pdf", "new.pdf"])
        result = get_knowledge_status(cm)

        assert "new.pdf" in result["issues"]["need_indexing"]
        assert result["summary"]["files_indexed"] is False

    @patch("services.knowledge_service.milvus_vector_counts")
    @patch("services.knowledge_service.query_unique_sources")
    @patch("services.knowledge_service._read_source_mapping")
    def test_orphaned_vectors(self, mock_mapping, mock_vectors, mock_counts):
        """Vectors exist for a source whose file was deleted."""
        from services.knowledge_service import get_knowledge_status

        mock_mapping.return_value = {"doc1.pdf": "t1"}
        mock_vectors.return_value = {"doc1.pdf", "deleted.pdf"}
        mock_counts.return_value = {"count": 100}

        cm = self._make_config_manager(["doc1.pdf"])
        result = get_knowledge_status(cm)

        assert "deleted.pdf" in result["issues"]["orphaned_vectors"]
        assert result["summary"]["vectors_clean"] is False

    @patch("services.knowledge_service.milvus_vector_counts")
    @patch("services.knowledge_service.query_unique_sources")
    @patch("services.knowledge_service._read_source_mapping")
    def test_empty_state(self, mock_mapping, mock_vectors, mock_counts):
        """Completely empty knowledge base."""
        from services.knowledge_service import get_knowledge_status

        mock_mapping.return_value = {}
        mock_vectors.return_value = set()
        mock_counts.return_value = {"count": 0}

        cm = self._make_config_manager([])
        result = get_knowledge_status(cm)

        assert result["config"]["total"] == 0
        assert result["files"]["total"] == 0
        assert result["vectors"]["total"] == 0
        assert result["summary"]["fully_synced_count"] == 0


# ── Knowledge Sync ─────────────────────────────────────────


class TestSyncKnowledge:
    """Tests for sync_knowledge."""

    def _make_config(self, sources, selected_sources=None):
        cfg = MagicMock()
        cfg.sources = list(sources)
        cfg.selected_sources = list(selected_sources or [])
        return cfg

    def _make_cm(self, sources, selected_sources=None):
        cm = MagicMock()
        cm.read_config.return_value = self._make_config(sources, selected_sources)
        return cm

    @patch("services.knowledge_service.query_unique_sources")
    @patch("services.knowledge_service._read_source_mapping")
    def test_sync_removes_orphaned_config(self, mock_mapping, mock_vectors):
        """Sync removes config entries that have no files."""
        from services.knowledge_service import sync_knowledge

        mock_mapping.return_value = {"doc1.pdf": "t1"}
        mock_vectors.return_value = {"doc1.pdf"}

        cm = self._make_cm(["doc1.pdf", "orphan.pdf"])
        vs = MagicMock()

        result = sync_knowledge(cm, vs)

        assert result["status"] == "success"
        assert "orphan.pdf" in result["results"]["removed_from_config"]
        cm.write_config.assert_called_once()

    @patch("services.knowledge_service.query_unique_sources")
    @patch("services.knowledge_service._read_source_mapping")
    def test_sync_no_issues(self, mock_mapping, mock_vectors):
        """Sync with fully synced state does nothing."""
        from services.knowledge_service import sync_knowledge

        mock_mapping.return_value = {"doc1.pdf": "t1"}
        mock_vectors.return_value = {"doc1.pdf"}

        cm = self._make_cm(["doc1.pdf"])
        vs = MagicMock()

        result = sync_knowledge(cm, vs)

        assert result["status"] == "success"
        assert result["results"]["indexed"] == []
        assert result["results"]["removed_from_config"] == []

    @patch("services.knowledge_service.query_unique_sources")
    @patch("services.knowledge_service._read_source_mapping")
    def test_sync_cleanup_orphaned_vectors(self, mock_mapping, mock_vectors):
        """Sync with cleanup=True removes orphaned vectors."""
        from services.knowledge_service import sync_knowledge

        mock_mapping.return_value = {"doc1.pdf": "t1"}
        mock_vectors.return_value = {"doc1.pdf", "ghost.pdf"}

        cm = self._make_cm(["doc1.pdf"])
        vs = MagicMock()
        vs.delete_by_source = MagicMock()

        result = sync_knowledge(cm, vs, cleanup=True)

        vs.delete_by_source.assert_called_once_with("ghost.pdf")
        assert "ghost.pdf" in result["results"]["removed_vectors"]


# ── Delete Knowledge Source ────────────────────────────────


class TestDeleteKnowledgeSource:
    """Tests for delete_knowledge_source."""

    def _make_cm_with_source(self, source_name):
        cfg = MagicMock()
        cfg.sources = [source_name]
        cfg.selected_sources = [source_name]
        cm = MagicMock()
        cm.read_config.return_value = cfg
        return cm

    @patch("services.knowledge_service._write_source_mapping")
    @patch("services.knowledge_service._read_source_mapping")
    @patch("services.knowledge_service.os.remove")
    @patch("services.knowledge_service.os.path.exists", return_value=True)
    @patch("services.knowledge_service.os.listdir", return_value=[])
    @patch("services.knowledge_service.os.rmdir")
    def test_delete_all_layers(
        self, mock_rmdir, mock_listdir, mock_exists, mock_remove,
        mock_read_map, mock_write_map,
    ):
        """delete_knowledge_source removes from config, vectors, and file."""
        from services.knowledge_service import delete_knowledge_source

        mock_read_map.return_value = {"test.pdf": "task-abc"}
        cm = self._make_cm_with_source("test.pdf")
        vs = MagicMock()
        vs.delete_by_source = MagicMock()

        result = delete_knowledge_source("test.pdf", cm, vs, delete_file=True)

        assert result["status"] == "success"
        assert result["results"]["removed_from_config"] is True
        assert result["results"]["deleted_vectors"] is True
        assert result["results"]["deleted_file"] is True
        cm.write_config.assert_called_once()
        vs.delete_by_source.assert_called_once_with("test.pdf")

    def test_delete_source_not_in_config(self):
        """Deleting a source not in config still succeeds (partial ops)."""
        from services.knowledge_service import delete_knowledge_source

        cfg = MagicMock()
        cfg.sources = []
        cfg.selected_sources = []
        cm = MagicMock()
        cm.read_config.return_value = cfg
        vs = MagicMock()

        with patch("services.knowledge_service._read_source_mapping", return_value={}):
            result = delete_knowledge_source("missing.pdf", cm, vs, delete_file=True)

        assert result["status"] == "success"
        assert result["results"]["removed_from_config"] is False


# ── Delete Source From Config ──────────────────────────────


class TestDeleteSourceFromConfig:
    """Tests for delete_source_from_config (lighter delete)."""

    def test_delete_existing_source(self):
        from services.knowledge_service import delete_source_from_config

        cfg = MagicMock()
        cfg.sources = ["a.pdf", "b.pdf"]
        cfg.selected_sources = ["a.pdf"]
        cm = MagicMock()
        cm.read_config.return_value = cfg

        vs = MagicMock()
        vs.delete_by_source = MagicMock()

        result = delete_source_from_config("a.pdf", cm, vs)

        assert result["status"] == "success"
        cm.write_config.assert_called_once()

    def test_delete_nonexistent_returns_none(self):
        from services.knowledge_service import delete_source_from_config

        cfg = MagicMock()
        cfg.sources = ["b.pdf"]
        cm = MagicMock()
        cm.read_config.return_value = cfg

        result = delete_source_from_config("missing.pdf", cm, MagicMock())
        assert result is None


# ── Sources With Vector Counts ─────────────────────────────


class TestGetSourcesWithVectorCounts:
    """Tests for get_sources_with_vector_counts."""

    @patch("services.knowledge_service.query_source_counts")
    @patch("services.knowledge_service.milvus_vector_counts")
    def test_ready_state(self, mock_counts, mock_source_counts):
        from services.knowledge_service import get_sources_with_vector_counts

        mock_counts.return_value = {"exists": True, "count": 200}
        mock_source_counts.return_value = {"doc1.pdf": 100, "doc2.pdf": 100}

        cfg = MagicMock()
        cfg.sources = ["doc1.pdf", "doc2.pdf"]
        cm = MagicMock()
        cm.read_config.return_value = cfg

        result = get_sources_with_vector_counts(cm)

        assert result["status"] == "ready"
        assert result["total_vectors"] == 200

    @patch("services.knowledge_service.milvus_vector_counts")
    def test_not_initialized(self, mock_counts):
        from services.knowledge_service import get_sources_with_vector_counts

        mock_counts.return_value = {"exists": False}

        cfg = MagicMock()
        cfg.sources = ["doc1.pdf"]
        cm = MagicMock()
        cm.read_config.return_value = cfg

        result = get_sources_with_vector_counts(cm)

        assert result["status"] == "not_initialized"
        assert result["total_vectors"] == 0
