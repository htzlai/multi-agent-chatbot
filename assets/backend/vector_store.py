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
import glob
import json
import uuid
from typing import List, Tuple, Dict, Any
import os
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_milvus import Milvus
from langchain_core.documents import Document
from typing_extensions import List
from langchain_openai import OpenAIEmbeddings
from langchain_unstructured import UnstructuredLoader
from dotenv import load_dotenv
from logger import logger
from typing import Optional, Callable
import requests


class CustomEmbeddings:
    """Wraps qwen3 embedding model to match OpenAI format with parallel processing"""
    
    def __init__(
        self, 
        model: str = "Qwen3-Embedding-4B-Q8_0.gguf", 
        host: str = "http://qwen3-embedding:8000",
        max_workers: int = 10,
        batch_size: int = 100
    ):
        """Initialize CustomEmbeddings with parallel processing support.
        
        Args:
            model: Embedding model name
            host: Embedding service host URL
            max_workers: Maximum parallel workers for embedding requests
            batch_size: Batch size for processing (for future batching optimization)
        """
        self.model = model
        self.url = f"{host}/v1/embeddings"
        self.max_workers = max_workers
        self.batch_size = batch_size

    def _get_embedding(self, text: str) -> List[float]:
        """Get embedding for a single text (helper for parallel processing)."""
        try:
            response = requests.post(
                self.url,
                json={"input": text, "model": self.model},
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            return data["data"][0]["embedding"]
        except Exception as e:
            logger.warning(f"Failed to get embedding: {e}")
            # Return zero vector as fallback
            return [0.0] * 1536  # Common embedding dimension

    def __call__(self, texts: list[str]) -> list[list[float]]:
        """Get embeddings for multiple texts using parallel processing.
        
        Uses ThreadPoolExecutor to make parallel HTTP requests to the 
        embedding service, significantly improving throughput for batch processing.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        # For single text, use simple approach
        if len(texts) == 1:
            return [self._get_embedding(texts[0])]
        
        # For multiple texts, use parallel processing
        embeddings = [None] * len(texts)
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_index = {
                executor.submit(self._get_embedding, text): i 
                for i, text in enumerate(texts)
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    embeddings[index] = future.result()
                except Exception as e:
                    logger.warning(f"Embedding failed for index {index}: {e}")
                    embeddings[index] = [0.0] * 1536
        
        return embeddings

    
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of document texts. Required by Milvus library."""
        return self.__call__(texts)
    
    def embed_query(self, text: str) -> list[float]:
        """Embed a single query text. Required by Milvus library."""
        return self._get_embedding(text)


class VectorStore:
    """Vector store for document embedding and retrieval.

    Decoupled from ConfigManager - uses optional callbacks for source management.
    """

    # Default collection name for all documents
    DEFAULT_COLLECTION_NAME = "context"

    def __init__(
        self,
        embeddings=None,
        uri: str = "http://milvus:19530",
        on_source_deleted: Optional[Callable[[str], None]] = None,
        upload_dir: str = "uploads"
    ):
        """Initialize the vector store.

        Args:
            embeddings: Embedding model to use (defaults to OllamaEmbeddings)
            uri: Milvus connection URI
            on_source_deleted: Optional callback when a source is deleted
            upload_dir: Directory for storing uploaded files
        """
        try:
            self.embeddings = embeddings or CustomEmbeddings(model="qwen3-embedding-custom")
            self.uri = uri
            self.on_source_deleted = on_source_deleted
            self.upload_dir = upload_dir
            self._initialize_store()

            # Source to task_id mapping for file cleanup
            self._source_to_task_id: Dict[str, str] = {}
            self._load_source_mapping()

            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200
            )

            logger.debug({
                "message": "VectorStore initialized successfully"
            })
        except Exception as e:
            logger.error({
                "message": "Error initializing VectorStore",
                "error": str(e)
            }, exc_info=True)
            raise

    def _load_source_mapping(self) -> None:
        """Load source to task_id mapping from config file if exists."""
        mapping_file = os.path.join(self.upload_dir, "source_mapping.json")
        if os.path.exists(mapping_file):
            try:
                with open(mapping_file, "r", encoding="utf-8") as f:
                    self._source_to_task_id = json.load(f)
                logger.debug({
                    "message": "Loaded source mapping",
                    "count": len(self._source_to_task_id)
                })
            except Exception as e:
                logger.warning({
                    "message": "Failed to load source mapping",
                    "error": str(e)
                })
                self._source_to_task_id = {}

    def _save_source_mapping(self) -> None:
        """Save source to task_id mapping to config file."""
        try:
            os.makedirs(self.upload_dir, exist_ok=True)
            mapping_file = os.path.join(self.upload_dir, "source_mapping.json")
            with open(mapping_file, "w", encoding="utf-8") as f:
                json.dump(self._source_to_task_id, f, indent=2, ensure_ascii=False)
            logger.debug({
                "message": "Saved source mapping",
                "count": len(self._source_to_task_id)
            })
        except Exception as e:
            logger.error({
                "message": "Failed to save source mapping",
                "error": str(e)
            })

    def register_source(self, source_name: str, task_id: str) -> None:
        """Register a source with its task_id for file cleanup.

        Args:
            source_name: Original filename/source name
            task_id: UUID of the upload task
        """
        self._source_to_task_id[source_name] = task_id
        self._save_source_mapping()
        logger.debug({
            "message": "Registered source mapping",
            "source": source_name,
            "task_id": task_id
        })
    
    def _initialize_store(self):
        try:
            from pymilvus import connections, Collection, utility
            # First, ensure connection exists
            try:
                connections.connect(alias=self.alias, uri=self.uri)
            except Exception:
                pass  # Connection might already exist
            
            # Check if collection exists
            if utility.has_collection(self.DEFAULT_COLLECTION_NAME):
                self._store = Milvus(
                    embedding_function=self.embeddings,
                    collection_name=self.DEFAULT_COLLECTION_NAME,
                    connection_args={"uri": self.uri},
                    auto_id=True
                )
                logger.info(f"Connected to existing collection: {self.DEFAULT_COLLECTION_NAME}")
            else:
                # Create new collection
                self._store = Milvus(
                    embedding_function=self.embeddings,
                    collection_name=self.DEFAULT_COLLECTION_NAME,
                    connection_args={"uri": self.uri},
                    auto_id=True
                )
                logger.info(f"Created new collection: {self.DEFAULT_COLLECTION_NAME}")
        except Exception as e:
            logger.error(f"Error initializing vector store: {e}")
            # Fallback: try to create anyway
            self._store = Milvus(
                embedding_function=self.embeddings,
                collection_name=self.DEFAULT_COLLECTION_NAME,
                connection_args={"uri": self.uri},
                auto_id=True
            )
        logger.debug({
            "message": "Milvus vector store initialized",
            "uri": self.uri,
            "collection": self.DEFAULT_COLLECTION_NAME
        })

    def _load_documents(self, file_paths: List[str] = None, input_dir: str = None) -> List[str]:
        try:
            documents = []
            source_name = None
            
            if input_dir:
                source_name = os.path.basename(os.path.normpath(input_dir))
                logger.debug({
                    "message": "Loading files from directory",
                    "directory": input_dir,
                    "source": source_name
                })
                file_paths = glob.glob(os.path.join(input_dir, "**"), recursive=True)
                file_paths = [f for f in file_paths if os.path.isfile(f)]
            
            logger.info(f"Processing {len(file_paths)} files: {file_paths}")
            
            for file_path in file_paths:
                try:
                    if not source_name:
                        source_name = os.path.basename(file_path)
                        logger.info(f"Using filename as source: {source_name}")
                    
                    logger.info(f"Loading file: {file_path}")
                    
                    file_ext = os.path.splitext(file_path)[1].lower()
                    logger.info(f"File extension: {file_ext}")
                    
                    try:
                        loader = UnstructuredLoader(file_path)
                        docs = loader.load()
                        logger.info(f"Successfully loaded {len(docs)} documents from {file_path}")
                    except Exception as pdf_error:
                        logger.error(f'error with unstructured loader, trying to load from scratch')
                        file_text = None
                        if file_ext == ".pdf":
                            logger.info("Attempting PyPDF text extraction fallback")
                            try:
                                from pypdf import PdfReader
                                reader = PdfReader(file_path)
                                extracted_pages = []
                                for page in reader.pages:
                                    try:
                                        extracted_pages.append(page.extract_text() or "")
                                    except Exception as per_page_err:
                                        logger.info(f"Warning: failed to extract a page: {per_page_err}")
                                        extracted_pages.append("")
                                file_text = "\n\n".join(extracted_pages).strip()
                            except Exception as pypdf_error:
                                logger.info(f"PyPDF fallback failed: {pypdf_error}")
                                file_text = None

                        if not file_text:
                            logger.info("Falling back to raw text read of file contents")
                            try:
                                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                                    file_text = f.read()
                            except Exception as read_error:
                                logger.info(f"Fallback read failed: {read_error}")
                                file_text = ""

                        if file_text and file_text.strip():
                            docs = [Document(
                                page_content=file_text,
                                metadata={
                                    "source": source_name,
                                    "file_path": file_path,
                                    "filename": os.path.basename(file_path),
                                }
                            )]
                        else:
                            logger.info("Creating a simple document as fallback (no text extracted)")
                            docs = [Document(
                                page_content=f"Document: {os.path.basename(file_path)}",
                                metadata={
                                    "source": source_name,
                                    "file_path": file_path,
                                    "filename": os.path.basename(file_path),
                                }
                            )]
                    
                    for doc in docs:
                        if not doc.metadata:
                            doc.metadata = {}
                        
                        cleaned_metadata = {}
                        cleaned_metadata["source"] = source_name
                        cleaned_metadata["file_path"] = file_path
                        cleaned_metadata["filename"] = os.path.basename(file_path)
                        
                        for key, value in doc.metadata.items():
                            if key not in ["source", "file_path"]:
                                if isinstance(value, (list, dict, set)):
                                    cleaned_metadata[key] = str(value)
                                elif value is not None:
                                    cleaned_metadata[key] = str(value)
                        
                        doc.metadata = cleaned_metadata
                    documents.extend(docs)
                    logger.debug({
                        "message": "Loaded documents from file",
                        "file_path": file_path,
                        "document_count": len(docs)
                    })
                except Exception as e:
                    logger.error({
                        "message": "Error loading file",
                        "file_path": file_path,
                        "error": str(e)
                    }, exc_info=True)
                    continue

            logger.info(f"Total documents loaded: {len(documents)}")
            return documents
            
        except Exception as e:
            logger.error({
                "message": "Error loading documents",
                "error": str(e)
            }, exc_info=True)
            raise

    def index_documents(self, documents: List[Document]) -> List[Document]:
        try:
            logger.debug({
                "message": "Starting document indexing",
                "document_count": len(documents)
            })
            
            splits = self.text_splitter.split_documents(documents)
            logger.debug({
                "message": "Split documents into chunks",
                "chunk_count": len(splits)
            })
            
            self._store.add_documents(splits)
            self.flush_store()
            
            logger.debug({
                "message": "Document indexing completed"
            })            
        except Exception as e:
            logger.error({
                "message": "Error during document indexing",
                "error": str(e)
            }, exc_info=True)
            raise

    def flush_store(self):
        """
        Flush the Milvus collection to ensure that all added documents are persisted to disk.
        """
        try:
            from pymilvus import connections
            
            connections.connect(uri=self.uri)
            

            from pymilvus import utility
            utility.flush_all()
            
            logger.debug({
                "message": "Milvus store flushed (persisted to disk)"
            })
        except Exception as e:
            logger.error({
                "message": "Error flushing Milvus store",
                "error": str(e)
            }, exc_info=True)


    def get_documents(self, query: str, k: int = 8, sources: List[str] = None) -> List[Document]:
        """
        Get relevant documents using the retriever's invoke method.
        """
        try:
            search_kwargs = {"k": k}
            
            if sources:
                if len(sources) == 1:
                    filter_expr = f'source == "{sources[0]}"'
                else:
                    source_conditions = [f'source == "{source}"' for source in sources]
                    filter_expr = " || ".join(source_conditions)
                
                search_kwargs["expr"] = filter_expr
                logger.debug({
                    "message": "Retrieving with filter",
                    "filter": filter_expr
                })
            
            retriever = self._store.as_retriever(
                search_type="similarity",
                search_kwargs=search_kwargs
            )
            
            docs = retriever.invoke(query)
            logger.debug({
                "message": "Retrieved documents",
                "query": query,
                "document_count": len(docs)
            })
            
            return docs
        except Exception as e:
            logger.error({
                "message": "Error retrieving documents",
                "error": str(e)
            }, exc_info=True)
            return []

    def get_documents_with_scores(self, query: str, k: int = 8, sources: List[str] = None) -> Tuple[List[Document], List[float]]:
        """
        Get relevant documents with similarity scores from Milvus.

        Args:
            query: The search query
            k: Number of documents to retrieve
            sources: Optional list of source names to filter by

        Returns:
            Tuple of (documents, scores) where scores are similarity scores
        """
        try:
            from pymilvus import connections, Collection, DataType
            import numpy as np

            # Connect to Milvus
            connections.connect(uri=self.uri)

            collection = Collection(name=self.DEFAULT_COLLECTION_NAME)
            collection.load()

            # Generate query embedding
            query_embedding = self.embeddings.embed_query(query)

            # Build search parameters - detect metric type from index
            # First, try to get metric type from collection schema
            metric_type = "L2"  # Default fallback
            try:
                # Get index info to determine metric type
                indexes = collection.indexes
                if indexes and len(indexes) > 0:
                    index_params = indexes[0]._index_params
                    # Check for metric_type in params
                    if "metric_type" in index_params:
                        metric_type = index_params["metric_type"]
                    elif "params" in index_params and isinstance(index_params["params"], dict):
                        if "metric_type" in index_params["params"]:
                            metric_type = index_params["params"]["metric_type"]
            except Exception as e:
                logger.debug({"message": "Could not detect metric type, using default", "error": str(e)})

            search_params = {"metric_type": metric_type, "params": {}}

            # Build filter expression if sources specified
            filter_expr = None
            if sources:
                if len(sources) == 1:
                    filter_expr = f'source == "{sources[0]}"'
                else:
                    source_conditions = [f'source == "{source}"' for source in sources]
                    filter_expr = " || ".join(source_conditions)

            logger.debug({
                "message": "Searching with scores",
                "query": query,
                "k": k,
                "filter": filter_expr
            })

            # Perform search
            results = collection.search(
                data=[query_embedding],
                anns_field="vector",
                param=search_params,
                limit=k,
                expr=filter_expr,
                output_fields=["source", "text", "file_path", "filename"]
            )

            documents = []
            scores = []

            if results and len(results) > 0:
                for hit in results[0]:
                    # Get metadata
                    metadata = {
                        "source": hit.entity.get("source", "unknown"),
                        "file_path": hit.entity.get("file_path", ""),
                        "filename": hit.entity.get("filename", ""),
                        "score": float(hit.distance)  # IP metric: higher is better
                    }

                    # Get text content
                    text = hit.entity.get("text", "")

                    doc = Document(
                        page_content=text,
                        metadata=metadata
                    )
                    documents.append(doc)
                    scores.append(float(hit.distance))

            logger.debug({
                "message": "Retrieved documents with scores",
                "document_count": len(documents),
                "scores": scores[:5] if scores else []  # Log first 5 scores
            })

            return documents, scores

        except Exception as e:
            logger.error({
                "message": "Error retrieving documents with scores",
                "error": str(e)
            }, exc_info=True)
            return [], []

    def delete_by_source(self, source_name: str) -> bool:
        """Delete all vectors for a specific source from Milvus.

        This method deletes vectors matching the source name instead of deleting
        the entire collection, which allows other sources to remain intact.

        Args:
            source_name: Name of the source to delete

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            from pymilvus import connections, Collection

            connections.connect(uri=self.uri)

            # Use the default collection (all documents are stored together)
            collection = Collection(name=self.DEFAULT_COLLECTION_NAME)

            # Load collection for reading
            collection.load()

            # Build filter expression to delete by source
            # Escape special characters in source_name for the expression
            escaped_source = source_name.replace('"', '\\"')
            filter_expr = f'source == "{escaped_source}"'

            logger.debug({
                "message": "Deleting vectors by source",
                "source": source_name,
                "filter": filter_expr
            })

            # Delete entities matching the filter
            # Note: This requires the collection to have a 'source' field indexed
            try:
                # First, check if the field exists and is indexed
                schema = collection.schema
                fields = {field.name: field for field in schema.fields}

                if "source" in fields:
                    # Ensure source field is indexed for filtering
                    index_info = collection.indexes
                    has_source_index = any(
                        "source" in str(idx._index_params.get("field_name", ""))
                        for idx in index_info
                    )

                    if not has_source_index:
                        # For string fields, we cannot create STL_SORT index
                        # Instead, we'll use a different approach: query pks first, then delete by pk
                        logger.debug({
                            "message": "Cannot create STL_SORT index on string field, will use pk-based deletion"
                        })

                # Delete using the filter - for string fields we need to query pks first
                try:
                    # Query to get primary keys of entities matching the source
                    query_results = collection.query(
                        expr=filter_expr,
                        output_fields=["pk"]
                    )
                    
                    if query_results:
                        pks = [result["pk"] for result in query_results]
                        # Delete by primary keys
                        delete_result = collection.delete(f"pk in {pks}")
                        collection.flush()
                        logger.info({
                            "message": "Deleted vectors by source using pk-based deletion",
                            "source": source_name,
                            "delete_count": len(pks)
                        })
                    else:
                        logger.info({
                            "message": "No vectors found for source",
                            "source": source_name
                        })
                except Exception as query_error:
                    logger.warning({
                        "message": "Failed to delete vectors",
                        "source": source_name,
                        "error": str(query_error)
                    })

            except Exception as delete_error:
                logger.warning({
                    "message": "Failed to delete by filter, trying alternative approach",
                    "error": str(delete_error)
                })
                # Alternative: This shouldn't happen in normal operation
                # but we continue to cleanup other resources

            # ====== Delete original uploaded files ======
            if source_name in self._source_to_task_id:
                task_id = self._source_to_task_id[source_name]
                upload_path = os.path.join(self.upload_dir, task_id)

                if os.path.exists(upload_path):
                    try:
                        shutil.rmtree(upload_path)
                        logger.debug({
                            "message": "Deleted upload directory",
                            "path": upload_path
                        })
                    except Exception as file_error:
                        logger.warning({
                            "message": "Failed to delete upload directory",
                            "path": upload_path,
                            "error": str(file_error)
                        })

                # Remove from mapping
                del self._source_to_task_id[source_name]
                self._save_source_mapping()
            # ==============================================

            # Trigger callback to update config
            if self.on_source_deleted:
                self.on_source_deleted(source_name)

            return True

        except Exception as e:
            logger.error({
                "message": "Error deleting source",
                "source": source_name,
                "error": str(e)
            }, exc_info=True)
            return False

    def delete_collection(self, collection_name: str) -> bool:
        """Delete a source from Milvus (alias for delete_by_source).

        Note: This now deletes by source name instead of dropping the entire
        collection, as all documents share a single collection with source-based
        filtering.

        Args:
            collection_name: Source name to delete (passed from API)

        Returns:
            bool: True if successful, False otherwise
        """
        # Delegate to delete_by_source for proper source-based deletion
        return self.delete_by_source(collection_name)

    def delete_all_collections(self) -> bool:
        """Delete all vectors from the Milvus collection.

        This will clear all vectors from the 'context' collection while
        keeping the collection schema intact.

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            from pymilvus import Collection, utility
            collection = Collection(self.collection_name, using=self.alias)
            collection.load()
            
            # Get all primary keys
            all_pks = collection.query(
                expr="pk >= 0",
                output_fields=["pk"]
            )
            
            if all_pks:
                pks = [item["pk"] for item in all_pks]
                collection.delete(f"pk in {pks}")
                collection.flush()
            
            collection.release()
            logger.info("All vectors deleted successfully")
            return True
        except Exception as e:
            logger.error(f"Error deleting all collections: {e}", exc_info=True)
            return False


def create_vector_store_with_config(config_manager, uri: str = "http://milvus:19530") -> VectorStore:
    """Factory function to create a VectorStore with ConfigManager integration.

    Args:
        config_manager: ConfigManager instance for source management
        uri: Milvus connection URI

    Returns:
        VectorStore instance with source deletion callback
    """
    import os

    def handle_source_deleted(source_name: str):
        """Handle source deletion by updating config."""
        config = config_manager.read_config()
        if hasattr(config, 'sources') and source_name in config.sources:
            config.sources.remove(source_name)
            # Also remove from selected_sources if present
            if hasattr(config, 'selected_sources') and source_name in config.selected_sources:
                config.selected_sources.remove(source_name)
            config_manager.write_config(config)

    # Get upload directory from environment or use default
    upload_dir = os.getenv("UPLOAD_DIR", "uploads")

    return VectorStore(
        uri=uri,
        on_source_deleted=handle_source_deleted,
        upload_dir=upload_dir
    )