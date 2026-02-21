#
# SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""FastAPI backend server for the chatbot application.

This module provides the main HTTP API endpoints and WebSocket connections for:
- Real-time chat via WebSocket
- File upload and document ingestion
- Configuration management (models, sources, chat settings)
- Chat history management
- Vector store operations
"""

import asyncio
import base64
import json
import os
import uuid
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Set

from fastapi import FastAPI, File, Form, UploadFile, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware

from agent import ChatAgent
from config import ConfigManager
from logger import logger, log_request, log_response, log_error
from models import ChatIdRequest, ChatRenameRequest, SelectedModelRequest
from postgres_storage import PostgreSQLConversationStorage
from utils import process_and_ingest_files_background
from vector_store import create_vector_store_with_config

AUTH_ENABLED = os.getenv("SUPABASE_JWT_SECRET") is not None

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", 5432))
POSTGRES_DB = os.getenv("POSTGRES_DB", "chatbot")
POSTGRES_USER = os.getenv("POSTGRES_USER", "chatbot_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "chatbot_password")

config_manager = ConfigManager("./config.json")

postgres_storage = PostgreSQLConversationStorage(
    host=POSTGRES_HOST,
    port=POSTGRES_PORT,
    database=POSTGRES_DB,
    user=POSTGRES_USER,
    password=POSTGRES_PASSWORD,
    cache_ttl=21600  # 6小时 = 6 * 60 * 60 秒
)

vector_store = create_vector_store_with_config(config_manager)

vector_store._initialize_store()

agent: ChatAgent | None = None
indexing_tasks: Dict[str, str] = {}

# 并发连接管理
# active_connections: Dict[chat_id, Set[WebSocket]] - 每个 chat_id 可能多个连接
# connection_tasks: Dict[chat_id, asyncio.Task] - 每个 chat_id 的处理任务
active_connections: Dict[str, Set[WebSocket]] = {}
connection_tasks: Dict[str, asyncio.Task] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown tasks."""
    global agent
    logger.debug("Initializing PostgreSQL storage and agent...")
    
    try:
        await postgres_storage.init_pool()
        logger.info("PostgreSQL storage initialized successfully")
        logger.debug("Initializing ChatAgent...")
        agent = await ChatAgent.create(
            vector_store=vector_store,
            config_manager=config_manager,
            postgres_storage=postgres_storage
        )
        logger.info("ChatAgent initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize PostgreSQL storage: {e}")
        raise

    yield
    
    try:
        await postgres_storage.close()
        logger.debug("PostgreSQL storage closed successfully")
    except Exception as e:
        logger.error(f"Error closing PostgreSQL storage: {e}")


app = FastAPI(
    title="Chatbot API",
    description="Backend API for LLM-powered chatbot with RAG capabilities",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def handle_chat_messages(websocket: WebSocket, chat_id: str):
    """处理单个 chat_id 的消息，独立运行不阻塞其他连接。
    
    每个 WebSocket 连接创建一个独立的任务来执行查询，
    这样多个用户可以同时向不同的 chat_id 发送消息。
    
    支持 stop 消息中断生成，以及 WebSocket 断开时的资源清理。
    """
    stop_event = asyncio.Event()
    current_query_task = None
    
    try:
        # 发送历史消息
        history_messages = await postgres_storage.get_messages(chat_id)
        history = [postgres_storage._message_to_dict(msg) for i, msg in enumerate(history_messages) if i != 0]
        await websocket.send_json({"type": "history", "messages": history})
        
        while True:
            data = await websocket.receive_text()
            client_message = json.loads(data)
            
            # Handle stop message - interrupt ongoing generation
            if client_message.get("type") == "stop":
                stop_event.set()
                logger.info(f"Stop requested for chat {chat_id}")
                
                # 如果有正在运行的任务，取消它
                if current_query_task and not current_query_task.done():
                    current_query_task.cancel()
                    try:
                        await current_query_task
                    except asyncio.CancelledError:
                        pass
                
                await websocket.send_json({"type": "stopped", "message": "Generation stopped"})
                stop_event.clear()  # 重置以备下次查询
                continue
            
            new_message = client_message.get("message")
            image_id = client_message.get("image_id")
            
            if not new_message:
                continue
            
            image_data = None
            if image_id:
                image_data = await postgres_storage.get_image(image_id)
                logger.debug(f"Retrieved image data for image_id: {image_id}, data length: {len(image_data) if image_data else 0}")
            
            # Reset stop event for new query
            stop_event.clear()
            
            async def run_query():
                """在独立任务中运行查询"""
                try:
                    async for event in agent.query(
                        query_text=new_message, 
                        chat_id=chat_id, 
                        image_data=image_data,
                        stop_event=stop_event
                    ):
                        if stop_event.is_set():
                            logger.debug(f"Generation stopped for chat {chat_id}")
                            return
                        await websocket.send_json(event)
                except asyncio.CancelledError:
                    logger.debug(f"Query task cancelled for chat {chat_id}")
                    raise
                except Exception as query_error:
                    logger.error(f"Error in agent.query: {str(query_error)}", exc_info=True)
                    await websocket.send_json({"type": "error", "content": f"Error processing request: {str(query_error)}"})
            
            try:
                # 创建任务来运行查询
                current_query_task = asyncio.create_task(run_query())
                await current_query_task
            except asyncio.CancelledError:
                logger.info(f"Query was cancelled for chat {chat_id}")
            finally:
                current_query_task = None
            
            # Send final history after query completes or is stopped
            final_messages = await postgres_storage.get_messages(chat_id)
            final_history = [postgres_storage._message_to_dict(msg) for i, msg in enumerate(final_messages) if i != 0]
            await websocket.send_json({"type": "history", "messages": final_history})
            
    except WebSocketDisconnect:
        logger.info(f"Client disconnected from chat {chat_id}")
        # 设置 stop_event 以停止任何正在进行的生成
        stop_event.set()
        # 取消正在运行的任务
        if current_query_task and not current_query_task.done():
            current_query_task.cancel()
            try:
                await current_query_task
            except asyncio.CancelledError:
                pass
    except Exception as e:
        logger.error(f"Error in chat handler for {chat_id}: {str(e)}", exc_info=True)
    finally:
        # 确保清理
        stop_event.set()
        if current_query_task and not current_query_task.done():
            current_query_task.cancel()
        # 清理连接
        if chat_id in active_connections:
            active_connections[chat_id].discard(websocket)
            if not active_connections[chat_id]:
                del active_connections[chat_id]


@app.websocket("/ws/chat/{chat_id}")
async def websocket_endpoint(
    websocket: WebSocket, 
    chat_id: str,
    token: Optional[str] = Query(None)
):
    """WebSocket endpoint for real-time chat communication.
    
    支持真正的并发处理：
    - 每个 chat_id 的消息处理作为独立 asyncio.Task
    - 多个用户可以同时向不同的 chat_id 发送消息
    - llama.cpp 层面通过 --parallel 和 --cont-batching 支持真正的并发推理
    
    Args:
        websocket: WebSocket connection
        chat_id: Unique chat identifier
        token: Optional JWT token for authentication (required if AUTH_ENABLED)
    """
    if AUTH_ENABLED:
        try:
            from auth import verify_token
            if not token:
                await websocket.close(code=4001, reason="Authentication required")
                return
            user = verify_token(token)
            logger.debug(f"WebSocket authenticated for user: {user.get('sub')}")
        except Exception as e:
            await websocket.close(code=4001, reason=f"Authentication failed: {str(e)}")
            return
    
    logger.debug(f"WebSocket connection attempt for chat_id: {chat_id}")
    try:
        await websocket.accept()
        logger.debug(f"WebSocket connection accepted for chat_id: {chat_id}")
        
        # 注册连接
        if chat_id not in active_connections:
            active_connections[chat_id] = set()
        active_connections[chat_id].add(websocket)
        
        # 启动独立任务处理此连接的消息
        # 不再使用串行 while True，而是为每个连接创建独立任务
        task = asyncio.create_task(handle_chat_messages(websocket, chat_id))
        
        # 等待任务完成（连接断开）
        await task
        
    except WebSocketDisconnect:
        logger.debug(f"Client disconnected from chat {chat_id}")
    except Exception as e:
        logger.error(f"WebSocket error for chat {chat_id}: {str(e)}", exc_info=True)
    finally:
        # 清理
        if chat_id in active_connections:
            active_connections[chat_id].discard(websocket)
            if not active_connections[chat_id]:
                del active_connections[chat_id]


@app.post("/upload-image")
async def upload_image(image: UploadFile = File(...), chat_id: str = Form(...)):
    """Upload and store an image for chat processing.
    
    Args:
        image: Uploaded image file
        chat_id: Chat identifier for context
        
    Returns:
        Dictionary with generated image_id
    """
    image_data = await image.read()
    image_base64 = base64.b64encode(image_data).decode('utf-8')
    data_uri = f"data:{image.content_type};base64,{image_base64}"
    image_id = str(uuid.uuid4())
    await postgres_storage.store_image(image_id, data_uri)
    return {"image_id": image_id}


@app.post("/ingest")
async def ingest_files(files: Optional[List[UploadFile]] = File(None), background_tasks: BackgroundTasks = None):
    """Ingest documents for vector search and RAG.
    
    Args:
        files: List of uploaded files to process
        background_tasks: FastAPI background tasks manager
        
    Returns:
        Task information for tracking ingestion progress
    """
    try:
        log_request({"file_count": len(files) if files else 0}, "/ingest")
        
        task_id = str(uuid.uuid4())
        
        file_info = []
        for file in files:
            content = await file.read()
            file_info.append({
                "filename": file.filename,
                "content": content
            })
        
        indexing_tasks[task_id] = "queued"
        
        background_tasks.add_task(
            process_and_ingest_files_background,
            file_info,
            vector_store,
            config_manager,
            task_id,
            indexing_tasks
        )
        
        response = {
            "message": f"Files queued for processing. Indexing {len(files)} files in the background.",
            "files": [file.filename for file in files],
            "status": "queued",
            "task_id": task_id
        }
        
        log_response(response, "/ingest")
        return response
            
    except Exception as e:
        log_error(e, "/ingest")
        raise HTTPException(
            status_code=500,
            detail=f"Error queuing files for ingestion: {str(e)}"
        )


@app.get("/ingest/status/{task_id}")
async def get_indexing_status(task_id: str):
    """Get the status of a file ingestion task.
    
    Args:
        task_id: Unique task identifier
        
    Returns:
        Current task status
    """
    if task_id in indexing_tasks:
        return {"status": indexing_tasks[task_id]}
    else:
        raise HTTPException(status_code=404, detail="Task not found")


@app.get("/sources")
async def get_sources():
    """Get all available document sources."""
    try:
        config = config_manager.read_config()
        return {"sources": config.sources}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting sources: {str(e)}")


@app.get("/selected_sources")
async def get_selected_sources():
    """Get currently selected document sources for RAG."""
    try:
        config = config_manager.read_config()
        return {"sources": config.selected_sources}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting selected sources: {str(e)}")


@app.post("/selected_sources")
async def update_selected_sources(selected_sources: List[str]):
    """Update the selected document sources for RAG.
    
    Args:
        selected_sources: List of source names to use for retrieval
    """
    try:
        config_manager.updated_selected_sources(selected_sources)
        return {"status": "success", "message": "Selected sources updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating selected sources: {str(e)}")


@app.get("/selected_model")
async def get_selected_model():
    """Get the currently selected LLM model."""
    try:
        model = config_manager.get_selected_model()
        return {"model": model}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting selected model: {str(e)}")


@app.post("/selected_model")
async def update_selected_model(request: SelectedModelRequest):
    """Update the selected LLM model.
    
    Args:
        request: Model selection request with model name
    """
    try:
        logger.debug(f"Updating selected model to: {request.model}")
        config_manager.updated_selected_model(request.model)
        return {"status": "success", "message": "Selected model updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating selected model: {str(e)}")


@app.get("/available_models")
async def get_available_models():
    """Get list of all available LLM models."""
    try:
        models = config_manager.get_available_models()
        return {"models": models}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting available models: {str(e)}")


@app.get("/chats")
async def list_chats():
    """Get list of all chat conversations."""
    try:
        chat_ids = await postgres_storage.list_conversations()
        return {"chats": chat_ids}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing chats: {str(e)}")


@app.get("/chat_id")
async def get_chat_id():
    """Get the current active chat ID, creating a conversation if it doesn't exist."""
    try:
        config = config_manager.read_config()
        current_chat_id = config.current_chat_id
        
        if current_chat_id and await postgres_storage.exists(current_chat_id):
            return {
                "status": "success",
                "chat_id": current_chat_id
            }
        
        new_chat_id = str(uuid.uuid4())
        
        await postgres_storage.save_messages_immediate(new_chat_id, [])
        await postgres_storage.set_chat_metadata(new_chat_id, f"Chat {new_chat_id[:8]}")
        
        config_manager.updated_current_chat_id(new_chat_id)
        
        return {
            "status": "success",
            "chat_id": new_chat_id
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting chat ID: {str(e)}"
        )


@app.post("/chat_id")
async def update_chat_id(request: ChatIdRequest):
    """Update the current active chat ID.
    
    Args:
        request: Chat ID update request
    """
    try:
        config_manager.updated_current_chat_id(request.chat_id)
        return {
            "status": "success",
            "message": f"Current chat ID updated to {request.chat_id}",
            "chat_id": request.chat_id
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error updating chat ID: {str(e)}"
        )


@app.get("/chat/{chat_id}/metadata")
async def get_chat_metadata(chat_id: str):
    """Get metadata for a specific chat.
    
    Args:
        chat_id: Unique chat identifier
        
    Returns:
        Chat metadata including name
    """
    try:
        metadata = await postgres_storage.get_chat_metadata(chat_id)
        return metadata
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting chat metadata: {str(e)}"
        )


@app.post("/chat/rename")
async def rename_chat(request: ChatRenameRequest):
    """Rename a chat conversation.
    
    Args:
        request: Chat rename request with chat_id and new_name
    """
    try:
        await postgres_storage.set_chat_metadata(request.chat_id, request.new_name)
        return {
            "status": "success",
            "message": f"Chat {request.chat_id} renamed to {request.new_name}"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error renaming chat: {str(e)}"
        )


@app.post("/chat/new")
async def create_new_chat():
    """Create a new chat conversation and set it as current."""
    try:
        new_chat_id = str(uuid.uuid4())
        await postgres_storage.save_messages_immediate(new_chat_id, [])
        await postgres_storage.set_chat_metadata(new_chat_id, f"Chat {new_chat_id[:8]}")
        
        config_manager.updated_current_chat_id(new_chat_id)
        
        return {
            "status": "success",
            "message": "New chat created",
            "chat_id": new_chat_id
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error creating new chat: {str(e)}"
        )


@app.delete("/chat/{chat_id}")
async def delete_chat(chat_id: str):
    """Delete a specific chat and its messages.
    
    Args:
        chat_id: Unique chat identifier to delete
    """
    try:
        success = await postgres_storage.delete_conversation(chat_id)
        
        if success:
            return {
                "status": "success",
                "message": f"Chat {chat_id} deleted successfully"
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Chat {chat_id} not found"
            )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting chat: {str(e)}"
        )


@app.delete("/chats/clear")
async def clear_all_chats():
    """Clear all chat conversations and create a new default chat."""
    try:
        chat_ids = await postgres_storage.list_conversations()
        cleared_count = 0
        
        for chat_id in chat_ids:
            if await postgres_storage.delete_conversation(chat_id):
                cleared_count += 1
        
        new_chat_id = str(uuid.uuid4())
        await postgres_storage.save_messages_immediate(new_chat_id, [])
        await postgres_storage.set_chat_metadata(new_chat_id, f"Chat {new_chat_id[:8]}")
        
        config_manager.updated_current_chat_id(new_chat_id)
        
        return {
            "status": "success",
            "message": f"Cleared {cleared_count} chats and created new chat",
            "new_chat_id": new_chat_id,
            "cleared_count": cleared_count
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error clearing all chats: {str(e)}"
        )


@app.delete("/collections/{collection_name}")
async def delete_collection(collection_name: str):
    """Delete a document collection from the vector store.

    Args:
        collection_name: Name of the collection to delete
    """
    try:
        success = vector_store.delete_collection(collection_name)
        if success:
            return {"status": "success", "message": f"Collection '{collection_name}' deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail=f"Collection '{collection_name}' not found or could not be deleted")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting collection: {str(e)}")


# ============================================================
# RAG Test Endpoints - For debugging and verification
# ============================================================

@app.get("/test/rag")
async def test_rag_search(query: str, k: int = 8):
    """Test RAG retrieval with enhanced metadata.

    Args:
        query: Search query
        k: Number of documents to retrieve
    """
    import json
    from tools.mcp_servers.rag import search_documents

    result = await search_documents(query)
    result_data = json.loads(result)

    return result_data


@app.get("/test/vector-stats")
async def test_vector_stats():
    """Get vector store statistics."""
    from pymilvus import connections, Collection

    connections.connect(uri="http://milvus:19530")

    try:
        collection = Collection("context")
        collection.load()

        total_entities = collection.num_entities

        indexes = collection.indexes

        schema = collection.schema
        fields = [{"name": f.name, "type": str(f.dtype)} for f in schema.fields]

        return {
            "collection": "context",
            "total_entities": total_entities,
            "fields": fields,
            "index_count": len(indexes)
        }
    except Exception as e:
        return {"error": str(e)}


# ============================================================
# RAG Admin API - 管理员功能
# ============================================================

@app.get("/admin/rag/stats")
async def get_rag_stats():
    """Get comprehensive RAG system statistics."""
    import json
    from tools.mcp_servers.rag import search_documents

    # Get vector stats
    from pymilvus import connections, Collection
    connections.connect(uri="http://milvus:19530")
    collection = Collection("context")
    collection.load()

    # Get sources
    config_obj = config_manager.read_config()
    all_sources = config_obj.sources or []
    selected_sources = config_obj.selected_sources or []

    # Get conversations count
    chat_ids = await postgres_storage.list_conversations()

    return {
        "vector_store": {
            "collection": "context",
            "total_entities": collection.num_entities,
            "index_count": len(collection.indexes),
            "fields": [f.name for f in collection.schema.fields]
        },
        "documents": {
            "total_count": len(all_sources),
            "selected_count": len(selected_sources),
            "unselected_count": len(all_sources) - len(selected_sources)
        },
        "conversations": {
            "total_count": len(chat_ids)
        }
    }


@app.get("/admin/rag/sources")
async def get_rag_sources():
    """Get all sources with selection status."""
    config_obj = config_manager.read_config()
    all_sources = config_obj.sources or []
    selected_sources = config_obj.selected_sources or []

    sources_detail = []
    for src in all_sources:
        sources_detail.append({
            "name": src,
            "selected": src in selected_sources
        })

    return {
        "sources": sources_detail,
        "total_count": len(all_sources),
        "selected_count": len(selected_sources)
    }


@app.post("/admin/rag/sources/select")
async def select_sources(request: dict):
    """Select sources for RAG retrieval."""
    sources = request.get("sources", [])

    config_obj = config_manager.read_config()
    config_manager.updated_selected_sources(sources)

    return {
        "status": "success",
        "selected_count": len(sources),
        "sources": sources
    }


@app.post("/admin/rag/sources/select-all")
async def select_all_sources():
    """Select all sources for RAG retrieval."""
    config_obj = config_manager.read_config()
    all_sources = config_obj.sources or []

    config_manager.updated_selected_sources(all_sources)

    return {
        "status": "success",
        "selected_count": len(all_sources),
        "message": f"Selected all {len(all_sources)} sources"
    }


@app.post("/admin/rag/sources/deselect-all")
async def deselect_all_sources():
    """Deselect all sources."""
    config_manager.updated_selected_sources([])

    return {
        "status": "success",
        "selected_count": 0,
        "message": "Deselected all sources"
    }


@app.get("/admin/conversations")
async def get_all_conversations():
    """Get all conversations with metadata."""
    chat_ids = await postgres_storage.list_conversations()

    conversations = []
    for chat_id in chat_ids:
        metadata = await postgres_storage.get_chat_metadata(chat_id)
        messages = await postgres_storage.get_messages(chat_id, limit=1)

        conversations.append({
            "chat_id": chat_id,
            "name": metadata.get("name", f"Chat {chat_id[:8]}") if metadata else f"Chat {chat_id[:8]}",
            "message_count": len(messages),
            "created_at": metadata.get("created_at") if metadata else None
        })

    return {"conversations": conversations, "total_count": len(conversations)}


@app.get("/admin/conversations/{chat_id}/messages")
async def get_conversation_messages(chat_id: str, limit: int = 100):
    """Get messages for a specific conversation."""
    messages = await postgres_storage.get_messages(chat_id, limit=limit)

    message_list = []
    for msg in messages:
        message_list.append({
            "type": type(msg).__name__,
            "content": msg.content if hasattr(msg, 'content') else str(msg)
        })

    return {"chat_id": chat_id, "messages": message_list, "count": len(message_list)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)