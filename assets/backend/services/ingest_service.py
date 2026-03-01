# SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Ingestion business logic — file upload queueing and task tracking.

Unifies the ``indexing_tasks`` dict previously duplicated across
``routers/upload.py`` and ``routers/api_v1.py``.
"""

import os
import uuid
from typing import Any, Dict, List, Optional

from logger import logger

# Single source of truth for indexing task status.
# Previously duplicated in upload.py and api_v1.py as independent dicts.
_indexing_tasks: Dict[str, str] = {}


async def _process_and_ingest_files(
    file_info: List[dict],
    vector_store,
    config_manager,
    task_id: str,
    indexing_tasks: Dict[str, str],
) -> None:
    """Process and ingest files in the background.

    Args:
        file_info: List of file dicts with 'filename' and 'content' keys.
        vector_store: VectorStore instance for document indexing.
        config_manager: ConfigManager instance for updating sources.
        task_id: Unique identifier for this processing task.
        indexing_tasks: Dictionary to track task status.
    """
    try:
        logger.debug({
            "message": "Starting background file processing",
            "task_id": task_id,
            "file_count": len(file_info),
        })

        indexing_tasks[task_id] = "saving_files"

        permanent_dir = os.path.join("uploads", task_id)
        os.makedirs(permanent_dir, exist_ok=True)

        file_paths: List[str] = []
        file_names: List[str] = []

        for info in file_info:
            try:
                file_name = info["filename"]
                content = info["content"]

                file_path = os.path.join(permanent_dir, file_name)
                with open(file_path, "wb") as f:
                    f.write(content)

                file_paths.append(file_path)
                file_names.append(file_name)

                vector_store.register_source(file_name, task_id)

                logger.debug({
                    "message": "Saved file",
                    "task_id": task_id,
                    "filename": file_name,
                    "path": file_path,
                })
            except Exception as e:
                logger.error({
                    "message": f"Error saving file {info['filename']}",
                    "task_id": task_id,
                    "filename": info["filename"],
                    "error": str(e),
                }, exc_info=True)

        indexing_tasks[task_id] = "loading_documents"
        logger.debug({"message": "Loading documents", "task_id": task_id})

        try:
            documents = vector_store._load_documents(file_paths)

            logger.debug({
                "message": "Documents loaded, starting indexing",
                "task_id": task_id,
                "document_count": len(documents),
            })

            indexing_tasks[task_id] = "indexing_documents"
            vector_store.index_documents(documents)

            if file_names:
                config = config_manager.read_config()

                config_updated = False
                for file_name in file_names:
                    if file_name not in config.sources:
                        config.sources.append(file_name)
                        config_updated = True

                    vector_store.register_source(file_name, task_id)

                if config_updated:
                    config_manager.write_config(config)
                    logger.debug({
                        "message": "Updated config with new sources",
                        "task_id": task_id,
                        "sources": config.sources,
                    })

            indexing_tasks[task_id] = "completed"
            logger.debug({
                "message": "Background processing and indexing completed successfully",
                "task_id": task_id,
            })
        except Exception as e:
            indexing_tasks[task_id] = f"failed_during_indexing: {str(e)}"
            logger.error({
                "message": "Error during document loading or indexing",
                "task_id": task_id,
                "error": str(e),
            }, exc_info=True)

    except Exception as e:
        indexing_tasks[task_id] = f"failed: {str(e)}"
        logger.error({
            "message": "Error in background processing",
            "task_id": task_id,
            "error": str(e),
        }, exc_info=True)


def queue_ingestion(
    file_info: List[Dict[str, Any]],
    vector_store,
    config_manager,
    background_tasks,
) -> Dict[str, Any]:
    """Queue files for background ingestion.

    Args:
        file_info: List of ``{"filename": str, "content": bytes}`` dicts.
        vector_store: VectorStore instance for indexing.
        config_manager: ConfigManager for source tracking.
        background_tasks: FastAPI ``BackgroundTasks`` instance.

    Returns:
        Dict with ``task_id``, ``status``, ``files``, ``message``.
    """
    task_id = str(uuid.uuid4())
    _indexing_tasks[task_id] = "queued"

    background_tasks.add_task(
        _process_and_ingest_files,
        file_info,
        vector_store,
        config_manager,
        task_id,
        _indexing_tasks,
    )

    return {
        "task_id": task_id,
        "status": "queued",
        "files": [f["filename"] for f in file_info],
        "message": f"Files queued for processing. Indexing {len(file_info)} files in the background.",
    }


def get_task_status(task_id: str) -> Optional[str]:
    """Return the status string for a task, or None if not found."""
    return _indexing_tasks.get(task_id)


def start_reindex_task() -> str:
    """Create a new reindex task entry and return its ID."""
    task_id = str(uuid.uuid4())
    _indexing_tasks[task_id] = "started"
    return task_id
