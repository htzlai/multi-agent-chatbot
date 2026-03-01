# SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Knowledge-base business logic — status, sync, source management.

Consolidates logic from ``routers/knowledge.py`` and ``routers/sources.py``.
All Milvus access goes through ``infrastructure.milvus_client`` (R2 compliant).
"""

import json
import os
import shutil
import tempfile
import urllib.parse
from typing import Any, Dict, List, Optional, Set

from config import ConfigManager
from infrastructure.milvus_client import (
    get_collection,
    get_connection,
    get_vector_counts as milvus_vector_counts,
    query_source_counts,
    query_unique_sources,
)
from logger import logger

_UPLOADS_DIR = "/app/uploads"
_MAPPING_FILE = f"{_UPLOADS_DIR}/source_mapping.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_source_mapping() -> Dict[str, str]:
    """Read source_mapping.json, returning empty dict if missing."""
    if not os.path.exists(_MAPPING_FILE):
        return {}
    with open(_MAPPING_FILE, "r") as f:
        return json.load(f)


def _write_source_mapping(mapping: Dict[str, str]) -> None:
    """Write source_mapping.json."""
    with open(_MAPPING_FILE, "w") as f:
        json.dump(mapping, f)


# ---------------------------------------------------------------------------
# Knowledge status
# ---------------------------------------------------------------------------

def get_knowledge_status(config_manager: ConfigManager) -> Dict[str, Any]:
    """Get unified knowledge-base status across config, files, and vectors.

    Performs 3-layer reconciliation:
    1. Config sources (config.json)
    2. File sources (source_mapping.json)
    3. Vector sources (Milvus collection)
    """
    config = config_manager.read_config()
    config_sources = set(config.sources)
    selected_sources = set(config.selected_sources or [])

    file_sources = set(_read_source_mapping().keys())

    vector_sources = query_unique_sources()
    stats = milvus_vector_counts()
    total_vectors = stats.get("count", 0)

    # Analyze discrepancies
    orphaned_in_config = config_sources - file_sources
    untracked_files = file_sources - config_sources
    need_indexing = file_sources - vector_sources
    orphaned_vectors = vector_sources - file_sources
    config_without_vectors = config_sources - vector_sources
    fully_synced = config_sources & file_sources & vector_sources

    return {
        "status": "ok",
        "config": {
            "total": len(config_sources),
            "selected": len(selected_sources),
            "sources": list(config_sources),
        },
        "files": {"total": len(file_sources), "sources": list(file_sources)},
        "vectors": {"total": total_vectors, "sources": list(vector_sources)},
        "issues": {
            "orphaned_in_config": list(orphaned_in_config),
            "untracked_files": list(untracked_files),
            "need_indexing": list(need_indexing),
            "orphaned_vectors": list(orphaned_vectors),
            "config_without_vectors": list(config_without_vectors),
        },
        "summary": {
            "config_files_match": len(orphaned_in_config) == 0
            and len(untracked_files) == 0,
            "files_indexed": len(need_indexing) == 0,
            "vectors_clean": len(orphaned_vectors) == 0,
            "fully_synced_count": len(fully_synced),
            "config_has_vectors": len(config_without_vectors) == 0,
        },
    }


# ---------------------------------------------------------------------------
# Knowledge sync
# ---------------------------------------------------------------------------

def sync_knowledge(
    config_manager: ConfigManager,
    vector_store,
    *,
    cleanup: bool = False,
) -> Dict[str, Any]:
    """Synchronize knowledge base across all three layers.

    Steps:
    1. Load config + file + vector state
    2. Index files missing vectors
    3. Re-index config sources without vectors
    4. Remove orphaned config entries
    5. Optionally clean orphaned vectors
    """
    results: Dict[str, List] = {
        "indexed": [],
        "removed_from_config": [],
        "removed_vectors": [],
        "errors": [],
    }

    config = config_manager.read_config()
    config_sources = set(config.sources)
    source_mapping = _read_source_mapping()
    file_sources = set(source_mapping.keys())
    vector_sources = query_unique_sources()

    # Index files with no vectors
    need_indexing = file_sources - vector_sources
    if need_indexing:
        _index_missing_sources(
            need_indexing, source_mapping, vector_store, results
        )

    # Re-index config sources without vectors
    config_without_vectors = config_sources - vector_sources
    if config_without_vectors:
        _index_missing_sources(
            config_without_vectors, source_mapping, vector_store, results
        )

    # Remove orphaned config entries
    orphaned = config_sources - file_sources
    if orphaned:
        config.sources = [s for s in config.sources if s not in orphaned]
        if config.selected_sources:
            config.selected_sources = [
                s for s in config.selected_sources if s not in orphaned
            ]
        config_manager.write_config(config)
        results["removed_from_config"] = list(orphaned)

    # Clean up orphaned vectors
    if cleanup:
        orphaned_vectors = vector_sources - file_sources
        for source in orphaned_vectors:
            try:
                if hasattr(vector_store, "delete_by_source"):
                    vector_store.delete_by_source(source)
                    results["removed_vectors"].append(source)
            except Exception as e:
                results["errors"].append(
                    f"Error removing vector for {source}: {str(e)}"
                )

    return {
        "status": "success",
        "message": "Knowledge base synchronized",
        "results": results,
    }


def _index_missing_sources(
    sources: Set[str],
    source_mapping: Dict[str, str],
    vector_store,
    results: Dict[str, List],
) -> None:
    """Index files for sources that have no vectors yet."""
    task_ids = {
        source_mapping[s] for s in sources if s in source_mapping
    }
    for task_id in task_ids:
        task_dir = f"{_UPLOADS_DIR}/{task_id}"
        if not os.path.isdir(task_dir):
            continue
        for filename in os.listdir(task_dir):
            file_path = os.path.join(task_dir, filename)
            if os.path.isfile(file_path) and filename in sources:
                try:
                    documents = vector_store._load_documents([file_path])
                    if documents:
                        vector_store.index_documents(documents)
                        results["indexed"].append(filename)
                except Exception as e:
                    results["errors"].append(
                        f"Error indexing {filename}: {str(e)}"
                    )


# ---------------------------------------------------------------------------
# Source deletion (full: config + vectors + file)
# ---------------------------------------------------------------------------

def delete_knowledge_source(
    source_name: str,
    config_manager: ConfigManager,
    vector_store,
    *,
    delete_file: bool = True,
) -> Dict[str, Any]:
    """Delete a knowledge source from all three layers.

    Returns operation results dict.
    """
    decoded = urllib.parse.unquote(source_name)

    op_results = {
        "removed_from_config": False,
        "deleted_vectors": False,
        "deleted_file": False,
    }

    # 1. Remove from config
    config = config_manager.read_config()
    if decoded in config.sources:
        config.sources = [s for s in config.sources if s != decoded]
        if config.selected_sources:
            config.selected_sources = [
                s for s in config.selected_sources if s != decoded
            ]
        config_manager.write_config(config)
        op_results["removed_from_config"] = True

    # 2. Delete vectors
    try:
        if hasattr(vector_store, "delete_by_source"):
            vector_store.delete_by_source(decoded)
            op_results["deleted_vectors"] = True
    except Exception as e:
        logger.warning(f"Could not delete vectors: {e}")

    # 3. Delete file
    if delete_file:
        source_mapping = _read_source_mapping()
        if decoded in source_mapping:
            task_id = source_mapping[decoded]
            file_path = f"{_UPLOADS_DIR}/{task_id}/{decoded}"

            if os.path.exists(file_path):
                os.remove(file_path)
                op_results["deleted_file"] = True

            dir_path = f"{_UPLOADS_DIR}/{task_id}"
            if os.path.exists(dir_path) and not os.listdir(dir_path):
                os.rmdir(dir_path)

            del source_mapping[decoded]
            _write_source_mapping(source_mapping)

    return {
        "status": "success",
        "message": f"Knowledge source '{decoded}' deleted",
        "results": op_results,
    }


# ---------------------------------------------------------------------------
# Source management (from sources.py)
# ---------------------------------------------------------------------------

def delete_source_from_config(
    source_name: str,
    config_manager: ConfigManager,
    vector_store,
) -> Dict[str, Any]:
    """Delete a source from config and vector store (lighter than full delete)."""
    decoded = urllib.parse.unquote(source_name)

    config = config_manager.read_config()
    if decoded not in config.sources:
        return None  # caller should raise 404

    config.sources = [s for s in config.sources if s != decoded]
    if config.selected_sources:
        config.selected_sources = [
            s for s in config.selected_sources if s != decoded
        ]
    config_manager.write_config(config)

    try:
        if hasattr(vector_store, "delete_by_source"):
            vector_store.delete_by_source(decoded)
    except Exception as ve:
        logger.warning(f"Could not delete vectors for source {decoded}: {ve}")

    return {
        "status": "success",
        "message": f"Source '{decoded}' deleted successfully",
        "remaining_sources": config.sources,
    }


def get_sources_with_vector_counts(
    config_manager: ConfigManager,
) -> Dict[str, Any]:
    """Get all sources with their vector counts (R2-compliant via milvus_client)."""
    config = config_manager.read_config()
    sources = config.sources

    stats = milvus_vector_counts()
    if not stats.get("exists", False):
        return {
            "sources": sources,
            "total_vectors": 0,
            "source_vectors": {},
            "status": "not_initialized",
            "message": "No vectors in database. Upload documents to create vectors.",
        }

    source_vectors = query_source_counts(sources)
    total_vectors = stats.get("count", 0)

    return {
        "sources": sources,
        "total_vectors": total_vectors,
        "source_vectors": source_vectors,
        "status": "ready" if total_vectors > 0 else "empty",
        "message": f"{total_vectors} vectors for {sum(1 for v in source_vectors.values() if v > 0)} sources",
    }


def reindex_sources(
    config_manager: ConfigManager,
    vector_store,
    sources: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Re-index documents from uploads folder.

    If ``sources`` is None, only sources with zero vectors are re-indexed.
    """
    source_mapping = _read_source_mapping()
    if not source_mapping:
        return None  # caller should raise 404

    vector_counts_data = get_sources_with_vector_counts(config_manager)
    source_vectors = vector_counts_data.get("source_vectors", {})

    if sources:
        to_reindex = sources
    else:
        to_reindex = [
            source
            for source, count in source_vectors.items()
            if count == 0 and source in source_mapping
        ]

    if not to_reindex:
        return {
            "status": "success",
            "message": "All sources already have vectors. No reindexing needed.",
            "reindexed": [],
        }

    # Collect files
    task_ids = {source_mapping[s] for s in to_reindex if s in source_mapping}
    files_to_reindex = []
    for task_id in task_ids:
        task_dir = f"{_UPLOADS_DIR}/{task_id}"
        if not os.path.isdir(task_dir):
            continue
        for filename in os.listdir(task_dir):
            file_path = os.path.join(task_dir, filename)
            if os.path.isfile(file_path):
                if filename in to_reindex or not sources:
                    with open(file_path, "rb") as f:
                        content = f.read()
                    files_to_reindex.append(
                        {"filename": filename, "content": content}
                    )

    if not files_to_reindex:
        return {
            "status": "warning",
            "message": "No files found for reindexing",
            "reindexed": [],
        }

    indexed_count = 0
    for file_info in files_to_reindex:
        try:
            filename = file_info["filename"]
            content = file_info["content"]

            with tempfile.TemporaryDirectory() as tmpdir:
                temp_path = os.path.join(tmpdir, filename)
                with open(temp_path, "wb") as f:
                    f.write(content)

                documents = vector_store._load_documents([temp_path])
                if documents:
                    vector_store.index_documents(documents)
                    indexed_count += 1
                    logger.info(f"Reindexed: {filename}")

        except Exception as e:
            logger.error(f"Error reindexing {file_info['filename']}: {e}")

    return {
        "status": "success",
        "message": f"Reindexed {indexed_count} documents",
        "reindexed": [f["filename"] for f in files_to_reindex],
    }
