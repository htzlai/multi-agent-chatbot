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


@app.get("/sources/vector-counts")
async def get_sources_with_vector_counts():
    """Get all document sources with their vector counts in Milvus.
    
    This helps identify which documents have vectors and which don't.
    """
    try:
        from pymilvus import connections, Collection, utility
        
        connections.connect(uri="http://milvus:19530")
        
        config = config_manager.read_config()
        sources = config.sources
        
        # Check if collection exists
        if not utility.has_collection("context"):
            return {
                "sources": sources,
                "total_vectors": 0,
                "source_vectors": {},
                "status": "not_initialized",
                "message": "No vectors in database. Upload documents to create vectors."
            }
        
        collection = Collection("context")
        collection.load()
        
        # Get vector count per source
        source_vectors = {}
        for source in sources:
            try:
                result = collection.query(
                    expr=f'source == "{source}"',
                    output_fields=["pk"]
                )
                source_vectors[source] = len(result)
            except Exception:
                source_vectors[source] = 0
        
        total_vectors = collection.num_entities
        
        return {
            "sources": sources,
            "total_vectors": total_vectors,
            "source_vectors": source_vectors,
            "status": "ready" if total_vectors > 0 else "empty",
            "message": f"{total_vectors} vectors for {sum(1 for v in source_vectors.values() if v > 0)} sources"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting vector counts: {str(e)}")


@app.post("/sources/reindex")
async def reindex_sources(sources: List[str] = None):
    """Re-index documents from uploads folder.
    
    This will re-create vectors for documents that exist in /app/uploads/
    but have no vectors in Milvus.
    
    Args:
        sources: Optional list of specific sources to reindex. If not provided,
                 will reindex all sources that have files in uploads but no vectors.
    """
    import json
    import os
    
    try:
        # Load source mapping
        mapping_file = "/app/uploads/source_mapping.json"
        if not os.path.exists(mapping_file):
            raise HTTPException(status_code=404, detail="No source mapping found. Upload documents first.")
        
        with open(mapping_file, "r") as f:
            source_mapping = json.load(f)
        
        # Get vector counts
        vector_counts_resp = await get_sources_with_vector_counts()
        source_vectors = vector_counts_resp.get("source_vectors", {})
        
        # Determine which sources to reindex
        if sources:
            # Reindex only specified sources
            to_reindex = sources
        else:
            # Reindex sources that have files but no vectors
            to_reindex = [
                source for source, count in source_vectors.items()
                if count == 0 and source in source_mapping
            ]
        
        if not to_reindex:
            return {
                "status": "success",
                "message": "All sources already have vectors. No reindexing needed.",
                "reindexed": []
            }
        
        # Get unique task IDs
        task_ids = set()
        for source in to_reindex:
            if source in source_mapping:
                task_ids.add(source_mapping[source])
        
        # Collect files to reindex
        files_to_reindex = []
        for task_id in task_ids:
            task_dir = f"/app/uploads/{task_id}"
            if os.path.isdir(task_dir):
                for filename in os.listdir(task_dir):
                    file_path = os.path.join(task_dir, filename)
                    if os.path.isfile(file_path):
                        # Check if this file is in our reindex list
                        if filename in to_reindex or not sources:
                            with open(file_path, "rb") as f:
                                content = f.read()
                            files_to_reindex.append({
                                "filename": filename,
                                "content": content
                            })
        
        if not files_to_reindex:
            return {
                "status": "warning",
                "message": "No files found for reindexing",
                "reindexed": []
            }
        
        # Process files using vector store directly
        indexed_count = 0
        for file_info in files_to_reindex:
            try:
                filename = file_info["filename"]
                content = file_info["content"]
                
                # Save to temp location for processing
                import tempfile
                import shutil
                
                with tempfile.TemporaryDirectory() as tmpdir:
                    temp_path = os.path.join(tmpdir, filename)
                    with open(temp_path, "wb") as f:
                        f.write(content)
                    
                # Add to vector store
                from langchain_core.documents import Document
                
                # Load and index using vector store methods
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
            "reindexed": [f["filename"] for f in files_to_reindex]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reindexing sources: {str(e)}")


@app.delete("/sources/{source_name}")
async def delete_source(source_name: str):
    """Delete a knowledge source from config and vector store.

    Args:
        source_name: Name of the source to delete (URL encoded)
    """
    try:
        # Decode the source name
        import urllib.parse
        decoded_source_name = urllib.parse.unquote(source_name)

        # Read current config
        config = config_manager.read_config()

        if decoded_source_name not in config.sources:
            raise HTTPException(status_code=404, detail=f"Source '{decoded_source_name}' not found")

        # Remove from sources list
        config.sources = [s for s in config.sources if s != decoded_source_name]

        # Remove from selected_sources if present
        if config.selected_sources:
            config.selected_sources = [s for s in config.selected_sources if s != decoded_source_name]

        # Save updated config
        config_manager.write_config(config)

        # Try to delete vectors from vector store (if supported)
        try:
            # The vector store might support deleting by source
            if hasattr(vector_store, 'delete_by_source'):
                vector_store.delete_by_source(decoded_source_name)
        except Exception as ve:
            # Log but don't fail if vector deletion fails
            logger.warning(f"Could not delete vectors for source {decoded_source_name}: {ve}")

        return {
            "status": "success",
            "message": f"Source '{decoded_source_name}' deleted successfully",
            "remaining_sources": config.sources
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting source: {str(e)}")


# ============================================================
# Unified Knowledge Base Management API
# ============================================================

@app.get("/knowledge/status")
async def get_knowledge_status():
    """Get unified knowledge base status.
    
    Returns the status of all three layers:
    - config: documents registered in config.json
    - files: actual files in /app/uploads/
    - vectors: vectors in Milvus
    """
    import json
    import os
    
    try:
        # 1. Get config status
        config = config_manager.read_config()
        config_sources = set(config.sources)
        selected_sources = set(config.selected_sources or [])
        
        # 2. Get file status
        mapping_file = "/app/uploads/source_mapping.json"
        file_sources = set()
        if os.path.exists(mapping_file):
            with open(mapping_file, "r") as f:
                source_mapping = json.load(f)
                file_sources = set(source_mapping.keys())
        
        # 3. Get vector status
        from pymilvus import connections, Collection, utility
        connections.connect(uri="http://milvus:19530")
        
        vector_sources = set()
        total_vectors = 0
        
        if utility.has_collection("context"):
            collection = Collection("context")
            collection.load()
            total_vectors = collection.num_entities
            
            # Get unique sources from vectors
            try:
                result = collection.query(expr="pk >= 0", output_fields=["source"])
                vector_sources = set(item["source"] for item in result if "source" in item)
            except:
                pass
        
        # 4. Analyze status
        # Documents that are in config but have no file
        orphaned_in_config = config_sources - file_sources
        
        # Documents that have files but are not in config
        untracked_files = file_sources - config_sources
        
        # Documents that have files but no vectors
        need_indexing = file_sources - vector_sources
        
        # Documents that have vectors but no files (orphaned vectors)
        orphaned_vectors = vector_sources - file_sources
        
        # Documents that are in config but have no vectors (手动删除向量后)
        config_without_vectors = config_sources - vector_sources
        
        # Documents in config that also have files and vectors
        fully_synced = config_sources & file_sources & vector_sources

        return {
            "status": "ok",
            "config": {
                "total": len(config_sources),
                "selected": len(selected_sources),
                "sources": list(config_sources)
            },
            "files": {
                "total": len(file_sources),
                "sources": list(file_sources)
            },
            "vectors": {
                "total": total_vectors,
                "sources": list(vector_sources)
            },
            "issues": {
                "orphaned_in_config": list(orphaned_in_config),
                "untracked_files": list(untracked_files),
                "need_indexing": list(need_indexing),
                "orphaned_vectors": list(orphaned_vectors),
                "config_without_vectors": list(config_without_vectors)
            },
            "summary": {
                "config_files_match": len(orphaned_in_config) == 0 and len(untracked_files) == 0,
                "files_indexed": len(need_indexing) == 0,
                "vectors_clean": len(orphaned_vectors) == 0,
                "fully_synced_count": len(fully_synced),
                "config_has_vectors": len(config_without_vectors) == 0
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting knowledge status: {str(e)}")


@app.post("/knowledge/sync")
async def sync_knowledge(cleanup: bool = False):
    """Synchronize knowledge base across all three layers.
    
    This endpoint checks for inconsistencies and optionally fixes them:
    1. Removes config entries for deleted files
    2. Indexes files that have no vectors
    3. Removes vectors for non-existent files (if cleanup=true)
    
    Args:
        cleanup: If true, also delete orphaned vectors
    """
    import json
    import os
    
    try:
        results = {
            "indexed": [],
            "removed_from_config": [],
            "removed_vectors": [],
            "errors": []
        }
        
        # 1. Load current state
        config = config_manager.read_config()
        config_sources = set(config.sources)
        
        mapping_file = "/app/uploads/source_mapping.json"
        file_sources = set()
        if os.path.exists(mapping_file):
            with open(mapping_file, "r") as f:
                source_mapping = json.load(f)
                file_sources = set(source_mapping.keys())
        
        # 2. Get vector status
        from pymilvus import connections, Collection, utility
        connections.connect(uri="http://milvus:19530")
        
        vector_sources = set()
        if utility.has_collection("context"):
            collection = Collection("context")
            collection.load()
            try:
                result = collection.query(expr="pk >= 0", output_fields=["source"])
                vector_sources = set(item["source"] for item in result if "source" in item)
            except:
                pass
        
        # 3. Index files that have no vectors
        need_indexing = file_sources - vector_sources
        if need_indexing:
            # Get unique task IDs
            task_ids = set()
            for source in need_indexing:
                if source in source_mapping:
                    task_ids.add(source_mapping[source])
            
            # Index each file
            for task_id in task_ids:
                task_dir = f"/app/uploads/{task_id}"
                if os.path.isdir(task_dir):
                    for filename in os.listdir(task_dir):
                        file_path = os.path.join(task_dir, filename)
                        if os.path.isfile(file_path) and filename in need_indexing:
                            try:
                                documents = vector_store._load_documents([file_path])
                                if documents:
                                    vector_store.index_documents(documents)
                                    results["indexed"].append(filename)
                            except Exception as e:
                                results["errors"].append(f"Error indexing {filename}: {str(e)}")
        
        # 4. Remove from config if file doesn't exist
        orphaned = config_sources - file_sources
        if orphaned:
            config.sources = [s for s in config.sources if s not in orphaned]
            if config.selected_sources:
                config.selected_sources = [s for s in config.selected_sources if s not in orphaned]
            config_manager.write_config(config)
            results["removed_from_config"] = list(orphaned)
        
        # 5. Re-index config sources that have no vectors (手动删除向量后)
        config_without_vectors = config_sources - vector_sources
        if config_without_vectors:
            for source in config_without_vectors:
                if source in source_mapping:
                    task_id = source_mapping[source]
                    task_dir = f"/app/uploads/{task_id}"
                    if os.path.isdir(task_dir):
                        file_path = os.path.join(task_dir, source)
                        if os.path.exists(file_path):
                            try:
                                documents = vector_store._load_documents([file_path])
                                if documents:
                                    vector_store.index_documents(documents)
                                    results["indexed"].append(source)
                            except Exception as e:
                                results["errors"].append(f"Error reindexing {source}: {str(e)}")
        
        # 6. Clean up orphaned vectors (if cleanup=true)
        if cleanup:
            orphaned_vectors = vector_sources - file_sources
            for source in orphaned_vectors:
                try:
                    if hasattr(vector_store, 'delete_by_source'):
                        vector_store.delete_by_source(source)
                        results["removed_vectors"].append(source)
                except Exception as e:
                    results["errors"].append(f"Error removing vector for {source}: {str(e)}")
        
        return {
            "status": "success",
            "message": "Knowledge base synchronized",
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error syncing knowledge: {str(e)}")


@app.delete("/knowledge/sources/{source_name}")
async def delete_knowledge_source(source_name: str, delete_file: bool = True):
    """Delete a knowledge source completely.
    
    This will:
    1. Remove from config.json
    2. Delete vectors from Milvus
    3. Optionally delete the original file
    
    Args:
        source_name: Name of the source to delete (URL encoded)
        delete_file: If true, also delete the original file from /app/uploads/
    """
    import json
    import os
    import shutil
    
    try:
        import urllib.parse
        decoded_source_name = urllib.parse.unquote(source_name)
        
        results = {
            "removed_from_config": False,
            "deleted_vectors": False,
            "deleted_file": False
        }
        
        # 1. Remove from config
        config = config_manager.read_config()
        
        if decoded_source_name in config.sources:
            config.sources = [s for s in config.sources if s != decoded_source_name]
            
            if config.selected_sources:
                config.selected_sources = [s for s in config.selected_sources if s != decoded_source_name]
            
            config_manager.write_config(config)
            results["removed_from_config"] = True
        
        # 2. Delete vectors
        try:
            if hasattr(vector_store, 'delete_by_source'):
                vector_store.delete_by_source(decoded_source_name)
                results["deleted_vectors"] = True
        except Exception as e:
            logger.warning(f"Could not delete vectors: {e}")
        
        # 3. Delete file (if exists)
        if delete_file:
            mapping_file = "/app/uploads/source_mapping.json"
            if os.path.exists(mapping_file):
                with open(mapping_file, "r") as f:
                    source_mapping = json.load(f)
                
                if decoded_source_name in source_mapping:
                    task_id = source_mapping[decoded_source_name]
                    file_path = f"/app/uploads/{task_id}/{decoded_source_name}"
                    
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        results["deleted_file"] = True
                    
                    # Clean up empty directories
                    dir_path = f"/app/uploads/{task_id}"
                    if os.path.exists(dir_path) and not os.listdir(dir_path):
                        os.rmdir(dir_path)
                    
                    # Update mapping
                    del source_mapping[decoded_source_name]
                    with open(mapping_file, "w") as f:
                        json.dump(source_mapping, f)
        
        return {
            "status": "success",
            "message": f"Knowledge source '{decoded_source_name}' deleted",
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting knowledge source: {str(e)}")


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


@app.delete("/collections")
async def delete_all_collections(confirm: bool = False):
    """Delete all document collections from the vector store.

    This will clear all vectors from the vector database.
    
    WARNING: This is a destructive operation that cannot be undone!
    
    Args:
        confirm: Must be set to true to actually perform the deletion
    """
    if not confirm:
        raise HTTPException(
            status_code=400, 
            detail="This is a destructive operation. Add ?confirm=true to delete all vectors."
        )
    try:
        success = vector_store.delete_all_collections()
        if success:
            return {"status": "success", "message": "All vectors deleted successfully. Documents in /app/uploads/ are still preserved."}
        else:
            raise HTTPException(status_code=500, detail="Failed to delete collections")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting all collections: {str(e)}")


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
    from pymilvus import connections, Collection, utility

    connections.connect(uri="http://milvus:19530")

    try:
        # Check if collection exists
        if not utility.has_collection("context"):
            return {
                "collection": "context",
                "total_entities": 0,
                "fields": [],
                "index_count": 0,
                "status": "not_initialized",
                "message": "Collection does not exist. Upload documents to initialize."
            }
        
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
            "index_count": len(indexes),
            "status": "ready" if total_entities > 0 else "empty"
        }
    except Exception as e:
        return {"error": str(e)}


# ============================================================
# LlamaIndex Enhanced RAG Endpoints
# ============================================================

@app.get("/rag/llamaindex/config")
async def get_llamaindex_config():
    """Get LlamaIndex RAG configuration."""
    return {
        "status": "available",
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


from pydantic import BaseModel

# Pydantic models for LlamaIndex endpoints
class LlamaIndexQueryRequest(BaseModel):
    query: str
    sources: Optional[List[str]] = None
    use_cache: bool = True
    top_k: int = 10


@app.post("/rag/llamaindex/query")
async def llamaindex_query(request: LlamaIndexQueryRequest):
    """Query using LlamaIndex enhanced RAG.
    
    This endpoint uses LlamaIndex with advanced features:
    - Hybrid search (vector + keyword)
    - Multiple chunking strategies
    - Query caching
    - Custom Qwen3 embeddings
    """
    try:
        from enhanced_rag import enhanced_rag_query
        
        result = await enhanced_rag_query(
            query=request.query,
            sources=request.sources,
            use_cache=request.use_cache,
            top_k=request.top_k,
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error in LlamaIndex query: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing query: {str(e)}"
        )


@app.get("/rag/llamaindex/stats")
async def llamaindex_stats():
    """Get LlamaIndex RAG statistics."""
    try:
        from enhanced_rag import get_stats
        
        stats = get_stats()
        return stats
        
    except Exception as e:
        logger.error(f"Error getting LlamaIndex stats: {str(e)}")
        return {"error": str(e)}


@app.post("/rag/llamaindex/cache/clear")
async def llamaindex_cache_clear():
    """Clear the LlamaIndex query cache."""
    try:
        from enhanced_rag import get_query_cache
        
        cache = get_query_cache()
        cache.clear()
        
        return {
            "status": "success",
            "message": "Query cache cleared successfully"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error clearing cache: {str(e)}"
        )


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