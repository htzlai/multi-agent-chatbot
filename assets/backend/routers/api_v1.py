# SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""RESTful /api/v1 endpoints — versioned API with consistent {data} envelope.

Consolidates ALL backend routes under a single versioned prefix.
Delegates to service layer for business logic. No direct pymilvus imports.
"""

import base64
import json
import uuid
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, UploadFile
from pydantic import BaseModel

from dependencies.providers import (
    get_config_manager,
    get_postgres_storage,
    get_vector_store,
)
from errors import APIError, InternalError, NotFoundError, ValidationError
from models import ChatIdRequest, SelectedModelRequest
from services import chat_service, ingest_service, knowledge_service, rag_service

router = APIRouter(prefix="/api/v1")


# --------------- RAG ---------------


class RagQueryRequest(BaseModel):
    query: str
    sources: Optional[List[str]] = None
    top_k: int = 10
    use_hybrid: bool = True
    use_cache: bool = True
    use_reranker: bool = True
    rerank_top_k: int = 5
    use_hyde: bool = False


@router.post("/rag/query", tags=["rag"])
async def rag_query_v1(request: RagQueryRequest):
    """RAG query using hybrid search (BM25 + Vector)."""
    result = await rag_service.query(
        query=request.query,
        sources=request.sources,
        top_k=request.top_k,
        use_hybrid=request.use_hybrid,
        use_cache=request.use_cache,
        use_reranker=request.use_reranker,
        rerank_top_k=request.rerank_top_k,
        use_hyde=request.use_hyde,
    )
    return {"data": result}


@router.get("/rag/stats", tags=["rag"])
async def rag_stats_v1():
    """RAG system statistics."""
    return {"data": rag_service.get_stats()}


@router.get("/rag/config", tags=["rag"])
async def rag_config_v1():
    """RAG configuration and pipeline features."""
    return {
        "data": {
            "status": "available",
            "embedding_dimensions": 2560,
            "chunk_size": 512,
            "chunk_overlap": 128,
            "cache_ttl": 3600,
            "features": {
                "hybrid_search": True,
                "multiple_chunking": True,
                "query_cache": True,
                "custom_embeddings": True,
            },
            "chunk_strategies": ["auto", "semantic", "fixed", "code", "markdown"],
            "default_chunk_strategy": "auto",
            "default_top_k": 10,
        }
    }


@router.post("/rag/cache/clear", tags=["rag"])
async def rag_cache_clear_v1():
    """Clear the RAG query cache (Redis and memory)."""
    try:
        from infrastructure.cache import get_query_cache, get_redis_query_cache

        cache = get_query_cache()
        cache.clear()

        redis_cache = get_redis_query_cache()
        redis_cache.clear()

        return {
            "data": {
                "message": "Query cache cleared (both Redis and memory)",
            }
        }
    except Exception as e:
        raise InternalError(f"Error clearing cache: {str(e)}")


@router.get("/rag/cache/stats", tags=["rag"])
async def rag_cache_stats_v1():
    """Get query cache statistics (Redis and memory)."""
    try:
        from infrastructure.cache import get_query_cache, get_redis_query_cache

        memory_cache = get_query_cache()
        redis_cache = get_redis_query_cache()
        redis_stats = redis_cache.get_stats()

        return {
            "data": {
                "memory_cache": {
                    "entries": len(memory_cache.cache),
                    "ttl": memory_cache.ttl,
                },
                "redis_cache": redis_stats,
            }
        }
    except Exception as e:
        raise InternalError(f"Error getting cache stats: {str(e)}")


# --------------- Models (config) ---------------


@router.get("/models/selected", tags=["config"])
async def get_selected_model_v1(config_manager=Depends(get_config_manager)):
    """Get the currently selected LLM model."""
    try:
        model = config_manager.get_selected_model()
        return {"data": {"model": model}}
    except Exception as e:
        raise InternalError(f"Error getting selected model: {str(e)}")


@router.post("/models/selected", tags=["config"])
async def update_selected_model_v1(
    request: SelectedModelRequest,
    config_manager=Depends(get_config_manager),
):
    """Update the selected LLM model."""
    try:
        config_manager.updated_selected_model(request.model)
        return {"data": {"model": request.model, "message": "Selected model updated"}}
    except Exception as e:
        raise InternalError(f"Error updating selected model: {str(e)}")


@router.get("/models/available", tags=["config"])
async def get_available_models_v1(config_manager=Depends(get_config_manager)):
    """Get list of all available LLM models."""
    try:
        models = config_manager.get_available_models()
        return {"data": {"models": models}}
    except Exception as e:
        raise InternalError(f"Error getting available models: {str(e)}")


# --------------- Chats ---------------


@router.get("/chats", tags=["chats"])
async def list_chats_v1(postgres_storage=Depends(get_postgres_storage)):
    """List all conversations."""
    try:
        chat_ids = await chat_service.list_chats(postgres_storage)
        return {"data": chat_ids}
    except Exception as e:
        raise InternalError(f"Error listing chats: {str(e)}")


@router.post("/chats", tags=["chats"])
async def create_chat_v1(
    config_manager=Depends(get_config_manager),
    postgres_storage=Depends(get_postgres_storage),
):
    """Create a new chat session."""
    try:
        result = await chat_service.create_chat(postgres_storage, config_manager)
        return {"data": result}
    except Exception as e:
        raise InternalError(f"Error creating chat: {str(e)}")


@router.get("/chats/current", tags=["chats"])
async def get_current_chat_v1(
    config_manager=Depends(get_config_manager),
    postgres_storage=Depends(get_postgres_storage),
):
    """Get current active chat (creates one if needed)."""
    try:
        chat_id = await chat_service.get_or_create_current_chat(
            postgres_storage, config_manager,
        )
        return {"data": {"chat_id": chat_id}}
    except Exception as e:
        raise InternalError(str(e))


@router.patch("/chats/current", tags=["chats"])
async def update_current_chat_v1(
    request: ChatIdRequest,
    config_manager=Depends(get_config_manager),
):
    """Update current active chat."""
    try:
        config_manager.updated_current_chat_id(request.chat_id)
        return {
            "data": {
                "chat_id": request.chat_id,
                "message": f"Current chat updated to {request.chat_id}",
            }
        }
    except Exception as e:
        raise InternalError(str(e))


# --------------- Sources ---------------


@router.get("/sources", tags=["sources"])
async def get_sources_v1(config_manager=Depends(get_config_manager)):
    """Get all document sources."""
    try:
        config = config_manager.read_config()
        return {"data": config.sources}
    except Exception as e:
        raise InternalError(str(e))


@router.get("/sources/vector-counts", tags=["sources"])
async def get_sources_vector_counts_v1(
    config_manager=Depends(get_config_manager),
):
    """Get all document sources with their vector counts in Milvus."""
    try:
        return {"data": knowledge_service.get_sources_with_vector_counts(config_manager)}
    except Exception as e:
        raise InternalError(f"Error getting vector counts: {str(e)}")


@router.post("/sources/reindex", tags=["sources"])
async def reindex_sources_v1(
    sources: Optional[List[str]] = None,
    config_manager=Depends(get_config_manager),
    vector_store=Depends(get_vector_store),
):
    """Re-index documents from uploads folder."""
    try:
        result = knowledge_service.reindex_sources(
            config_manager, vector_store, sources=sources,
        )
        if result is None:
            raise NotFoundError("Source mapping", "upload")
        return {"data": result}
    except APIError:
        raise
    except Exception as e:
        raise InternalError(f"Error reindexing sources: {str(e)}")


@router.delete("/sources/{source_name}", tags=["sources"])
async def delete_source_v1(
    source_name: str,
    config_manager=Depends(get_config_manager),
    vector_store=Depends(get_vector_store),
):
    """Delete a knowledge source from config and vector store."""
    try:
        result = knowledge_service.delete_source_from_config(
            source_name, config_manager, vector_store,
        )
        if result is None:
            raise NotFoundError("Source", source_name)
        return {"data": result}
    except APIError:
        raise
    except Exception as e:
        raise InternalError(f"Error deleting source: {str(e)}")


@router.get("/selected-sources", tags=["sources"])
async def get_selected_sources_v1(config_manager=Depends(get_config_manager)):
    """Get currently selected sources."""
    try:
        config = config_manager.read_config()
        return {"data": config.selected_sources}
    except Exception as e:
        raise InternalError(str(e))


@router.post("/selected-sources", tags=["sources"])
async def update_selected_sources_v1(
    request: dict,
    config_manager=Depends(get_config_manager),
):
    """Set selected sources."""
    try:
        sources = request.get("sources", [])
        config_manager.updated_selected_sources(sources)
        return {"data": {"selected_sources": sources}}
    except Exception as e:
        raise InternalError(str(e))


# --------------- Upload / Ingest ---------------


@router.post("/upload/image", tags=["upload"])
async def upload_image_v1(
    image: UploadFile = File(...),
    chat_id: str = Form(...),
    storage=Depends(get_postgres_storage),
):
    """Upload and store an image for chat processing."""
    image_data = await image.read()
    image_base64 = base64.b64encode(image_data).decode("utf-8")
    data_uri = f"data:{image.content_type};base64,{image_base64}"
    image_id = str(uuid.uuid4())
    await storage.store_image(image_id, data_uri)
    return {"data": {"image_id": image_id}}


@router.post("/ingest", tags=["upload"])
async def ingest_files_v1(
    files: Optional[List[UploadFile]] = File(None),
    background_tasks: BackgroundTasks = None,
    vs=Depends(get_vector_store),
    config=Depends(get_config_manager),
):
    """Ingest documents for vector search and RAG."""
    try:
        file_info = []
        if files:
            for file in files:
                content = await file.read()
                file_info.append({"filename": file.filename, "content": content})

        response = ingest_service.queue_ingestion(
            file_info, vs, config, background_tasks,
        )
        return {"data": response}
    except Exception as e:
        raise InternalError(f"Error queuing files for ingestion: {str(e)}")


@router.get("/ingest/status/{task_id}", tags=["upload"])
async def get_ingest_status_v1(task_id: str):
    """Get the status of a file ingestion task."""
    status = ingest_service.get_task_status(task_id)
    if status is not None:
        return {"data": {"status": status}}
    raise NotFoundError("Ingest task", task_id)


# --------------- Knowledge ---------------


@router.get("/knowledge/status", tags=["knowledge"])
async def get_knowledge_status_v1(config_manager=Depends(get_config_manager)):
    """Get unified knowledge base status across config, files, and vectors."""
    try:
        return {"data": knowledge_service.get_knowledge_status(config_manager)}
    except Exception as e:
        raise InternalError(f"Error getting knowledge status: {str(e)}")


@router.post("/knowledge/sync", tags=["knowledge"])
async def sync_knowledge_v1(
    cleanup: bool = False,
    config_manager=Depends(get_config_manager),
    vector_store=Depends(get_vector_store),
):
    """Synchronize knowledge base across all three layers."""
    try:
        result = knowledge_service.sync_knowledge(
            config_manager, vector_store, cleanup=cleanup,
        )
        return {"data": result}
    except Exception as e:
        raise InternalError(f"Error syncing knowledge: {str(e)}")


@router.delete("/knowledge/sources/{source_name}", tags=["knowledge"])
async def delete_knowledge_source_v1(
    source_name: str,
    delete_file: bool = True,
    config_manager=Depends(get_config_manager),
    vector_store=Depends(get_vector_store),
):
    """Delete a knowledge source completely (config + vectors + file)."""
    try:
        result = knowledge_service.delete_knowledge_source(
            source_name, config_manager, vector_store, delete_file=delete_file,
        )
        return {"data": result}
    except Exception as e:
        raise InternalError(f"Error deleting knowledge source: {str(e)}")


# --------------- Chat Individual Operations ---------------


class ChatRenameRequest(BaseModel):
    title: str


@router.get("/chats/{chat_id}/messages", tags=["chats"])
async def get_chat_messages_v1(
    chat_id: str,
    limit: Optional[int] = Query(None, ge=1, le=1000),
    postgres_storage=Depends(get_postgres_storage),
):
    """Get message history for a chat."""
    try:
        messages_data = await chat_service.get_chat_messages(
            postgres_storage, chat_id, limit=limit,
        )
        return {"data": messages_data}
    except Exception as e:
        raise InternalError(str(e))


@router.get("/chats/{chat_id}/metadata", tags=["chats"])
async def get_chat_metadata_v1(
    chat_id: str,
    postgres_storage=Depends(get_postgres_storage),
):
    """Get chat metadata."""
    try:
        metadata = await postgres_storage.get_chat_metadata(chat_id)
        return {"data": metadata}
    except Exception as e:
        raise InternalError(str(e))


@router.patch("/chats/{chat_id}/metadata", tags=["chats"])
async def update_chat_metadata_v1(
    chat_id: str,
    request: ChatRenameRequest,
    postgres_storage=Depends(get_postgres_storage),
):
    """Update chat metadata (e.g. rename)."""
    try:
        await postgres_storage.set_chat_metadata(chat_id, request.title)
        return {
            "data": {
                "chat_id": chat_id,
                "title": request.title,
                "message": "Chat metadata updated",
            }
        }
    except Exception as e:
        raise InternalError(str(e))


@router.delete("/chats/{chat_id}", tags=["chats"])
async def delete_chat_v1(
    chat_id: str,
    postgres_storage=Depends(get_postgres_storage),
):
    """Delete a specific chat."""
    try:
        success = await postgres_storage.delete_conversation(chat_id)
        if success:
            return {
                "data": {
                    "chat_id": chat_id,
                    "message": "Chat deleted successfully",
                }
            }
        raise NotFoundError("Chat", chat_id)
    except APIError:
        raise
    except Exception as e:
        raise InternalError(str(e))


@router.delete("/chats", tags=["chats"])
async def clear_all_chats_v1(postgres_storage=Depends(get_postgres_storage)):
    """Clear all chats."""
    try:
        chat_ids = await postgres_storage.list_conversations()
        deleted_count = 0
        for chat_id in chat_ids:
            success = await postgres_storage.delete_conversation(chat_id)
            if success:
                deleted_count += 1

        return {
            "data": {
                "deleted_count": deleted_count,
                "message": f"Successfully deleted {deleted_count} chats",
            }
        }
    except Exception as e:
        raise InternalError(str(e))


# --------------- Admin ---------------


@router.delete("/admin/collections/{collection_name}", tags=["admin"])
async def delete_collection_v1(
    collection_name: str,
    vector_store=Depends(get_vector_store),
):
    """Delete a document collection from the vector store."""
    try:
        success = vector_store.delete_collection(collection_name)
        if success:
            return {
                "data": {
                    "message": f"Collection '{collection_name}' deleted successfully",
                }
            }
        raise NotFoundError("Collection", collection_name)
    except APIError:
        raise
    except Exception as e:
        raise InternalError(f"Error deleting collection: {str(e)}")


@router.delete("/admin/collections", tags=["admin"])
async def delete_all_collections_v1(
    confirm: bool = False,
    vector_store=Depends(get_vector_store),
):
    """Delete all document collections. WARNING: destructive, requires ?confirm=true."""
    if not confirm:
        raise ValidationError(
            "This is a destructive operation. Add ?confirm=true to delete all vectors."
        )
    try:
        success = vector_store.delete_all_collections()
        if success:
            return {
                "data": {
                    "message": "All vectors deleted. Documents in /app/uploads/ are still preserved.",
                }
            }
        raise InternalError("Failed to delete collections")
    except APIError:
        raise
    except Exception as e:
        raise InternalError(f"Error deleting all collections: {str(e)}")


@router.get("/admin/test/rag", tags=["admin"])
async def test_rag_search_v1(query: str, k: int = 8):
    """Test RAG retrieval with enhanced metadata."""
    from tools.mcp_servers.rag import search_documents

    result = await search_documents(query)
    return {"data": json.loads(result)}


@router.get("/admin/test/vector-stats", tags=["admin"])
async def test_vector_stats_v1():
    """Get vector store statistics."""
    try:
        from infrastructure.milvus_client import get_collection_stats

        return {"data": get_collection_stats()}
    except Exception as e:
        raise InternalError(f"Error getting vector stats: {str(e)}")


@router.get("/admin/rag/stats", tags=["admin"])
async def get_admin_rag_stats_v1(
    config_manager=Depends(get_config_manager),
    postgres_storage=Depends(get_postgres_storage),
):
    """Get comprehensive RAG system statistics."""
    from infrastructure.milvus_client import get_collection_stats

    stats = get_collection_stats()
    config_obj = config_manager.read_config()
    all_sources = config_obj.sources or []
    selected_sources = config_obj.selected_sources or []
    chat_ids = await postgres_storage.list_conversations()

    return {
        "data": {
            "vector_store": {
                "collection": stats["collection"],
                "total_entities": stats["total_entities"],
                "index_count": stats["index_count"],
                "fields": stats.get("field_names", []),
            },
            "documents": {
                "total_count": len(all_sources),
                "selected_count": len(selected_sources),
                "unselected_count": len(all_sources) - len(selected_sources),
            },
            "conversations": {"total_count": len(chat_ids)},
        }
    }


@router.get("/admin/rag/sources", tags=["admin"])
async def get_admin_rag_sources_v1(config_manager=Depends(get_config_manager)):
    """Get all sources with selection status."""
    config_obj = config_manager.read_config()
    all_sources = config_obj.sources or []
    selected_sources = config_obj.selected_sources or []

    sources_detail = [
        {"name": src, "selected": src in selected_sources} for src in all_sources
    ]

    return {
        "data": {
            "sources": sources_detail,
            "total_count": len(all_sources),
            "selected_count": len(selected_sources),
        }
    }


@router.post("/admin/rag/sources/select", tags=["admin"])
async def select_sources_v1(
    request: dict,
    config_manager=Depends(get_config_manager),
):
    """Select sources for RAG retrieval."""
    sources = request.get("sources", [])
    config_manager.updated_selected_sources(sources)

    return {
        "data": {
            "selected_count": len(sources),
            "sources": sources,
        }
    }


@router.post("/admin/rag/sources/select-all", tags=["admin"])
async def select_all_sources_v1(config_manager=Depends(get_config_manager)):
    """Select all sources for RAG retrieval."""
    config_obj = config_manager.read_config()
    all_sources = config_obj.sources or []
    config_manager.updated_selected_sources(all_sources)

    return {
        "data": {
            "selected_count": len(all_sources),
            "message": f"Selected all {len(all_sources)} sources",
        }
    }


@router.post("/admin/rag/sources/deselect-all", tags=["admin"])
async def deselect_all_sources_v1(config_manager=Depends(get_config_manager)):
    """Deselect all sources."""
    config_manager.updated_selected_sources([])

    return {
        "data": {
            "selected_count": 0,
            "message": "Deselected all sources",
        }
    }


@router.get("/admin/conversations", tags=["admin"])
async def get_all_conversations_v1(
    postgres_storage=Depends(get_postgres_storage),
):
    """Get all conversations with metadata."""
    chat_ids = await postgres_storage.list_conversations()

    conversations = []
    for chat_id in chat_ids:
        metadata = await postgres_storage.get_chat_metadata(chat_id)
        messages = await postgres_storage.get_messages(chat_id, limit=1)

        conversations.append(
            {
                "chat_id": chat_id,
                "name": metadata.get("name", f"Chat {chat_id[:8]}")
                if metadata
                else f"Chat {chat_id[:8]}",
                "message_count": len(messages),
                "created_at": metadata.get("created_at") if metadata else None,
            }
        )

    return {"data": {"conversations": conversations, "total_count": len(conversations)}}


@router.get("/admin/conversations/{chat_id}/messages", tags=["admin"])
async def get_admin_conversation_messages_v1(
    chat_id: str,
    limit: int = 100,
    postgres_storage=Depends(get_postgres_storage),
):
    """Get messages for a specific conversation (admin view)."""
    messages = await postgres_storage.get_messages(chat_id, limit=limit)

    message_list = [
        {
            "type": type(msg).__name__,
            "content": msg.content if hasattr(msg, "content") else str(msg),
        }
        for msg in messages
    ]

    return {"data": {"chat_id": chat_id, "messages": message_list, "count": len(message_list)}}
