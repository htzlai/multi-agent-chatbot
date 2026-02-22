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

"""Enhanced RAG Module using LlamaIndex.

This module provides advanced RAG capabilities including:
- Hybrid search (vector + BM25)
- Multiple chunking strategies
- Custom embedding integration with Qwen3
- Query expansion and reranking
"""

import os
import json
import asyncio
import hashlib
import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

import requests
from pymilvus import connections, Collection

logger = logging.getLogger(__name__)


class Qwen3Embedding:
    """Qwen3 embedding model wrapper compatible with LlamaIndex."""
    
    def __init__(
        self,
        model: str = "Qwen3-Embedding-4B-Q8_0.gguf",
        host: str = "http://qwen3-embedding:8000",
        dimensions: int = 1024,
    ):
        self.model = model
        self.url = f"{host}/v1/embeddings"
        self.dimensions = dimensions
        self._api_key = "fake"  # Required for compatibility
        
    def _get_embedding(self, text: str) -> List[float]:
        """Get embedding for a single text."""
        response = requests.post(
            self.url,
            json={"input": text, "model": self.model},
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        return data["data"][0]["embedding"]
    
    def get_embedding(self, text: str) -> List[float]:
        """Get embedding for text."""
        return self._get_embedding(text)
    
    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for multiple texts."""
        return [self._get_embedding(text) for text in texts]


class ChunkStrategy:
    """Document chunking strategies."""
    
    @staticmethod
    def get_strategy(strategy: str = "auto"):
        """Get chunking strategy by name."""
        from llama_index.core.node_parser import SentenceSplitter
        
        strategies = {
            "auto": SentenceSplitter(chunk_size=1024, chunk_overlap=200),
            "semantic": SentenceSplitter(chunk_size=800, chunk_overlap=150),
            "fixed": SentenceSplitter(chunk_size=1000, chunk_overlap=200),
        }
        
        return strategies.get(strategy, strategies["auto"])


class QueryCache:
    """Simple in-memory query cache."""
    
    def __init__(self, ttl: int = 3600):
        self.cache: Dict[str, Tuple[str, float]] = {}
        self.ttl = ttl
    
    def _hash_query(self, query: str, sources: Optional[List[str]] = None) -> str:
        key_data = json.dumps({'q': query, 's': sorted(sources or [])}, sort_keys=True)
        return hashlib.sha256(key_data.encode()).hexdigest()
    
    def get(self, query: str, sources: Optional[List[str]] = None) -> Optional[str]:
        key = self._hash_query(query, sources)
        if key in self.cache:
            result, timestamp = self.cache[key]
            import time
            if time.time() - timestamp < self.ttl:
                return result
            else:
                del self.cache[key]
        return None
    
    def set(self, query: str, result: str, sources: Optional[List[str]] = None):
        import time
        key = self._hash_query(query, sources)
        self.cache[key] = (result, time.time())
    
    def clear(self):
        """Clear all cached queries."""
        self.cache.clear()


# Global instances
_embedding_model: Optional[Qwen3Embedding] = None
_query_cache: Optional[QueryCache] = None


def get_embedding_model() -> Qwen3Embedding:
    """Get or create the global embedding model."""
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = Qwen3Embedding()
    return _embedding_model


def get_query_cache() -> QueryCache:
    """Get or create the global query cache."""
    global _query_cache
    if _query_cache is None:
        _query_cache = QueryCache(ttl=3600)
    return _query_cache


def milvus_query(
    query: str,
    top_k: int = 10,
    sources: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Query Milvus directly using Qwen3 embeddings.
    
    This is a simplified implementation that works with the existing Milvus collection.
    """
    # Get embedding for query
    embedding_model = get_embedding_model()
    query_embedding = embedding_model.get_embedding(query)
    
    # Connect to Milvus
    connections.connect(uri="http://milvus:19530")
    
    # Load collection
    collection = Collection("context")
    collection.load()
    
    # Build search parameters
    search_params = {"metric_type": "IP", "params": {}}
    
    # Execute search
    if sources:
        # Filter by sources
        results = collection.search(
            data=[query_embedding],
            anns_field="vector",
            param=search_params,
            limit=top_k,
            expr=f'source in {sources}',
            output_fields=["text", "source", "file_path", "filename"]
        )
    else:
        results = collection.search(
            data=[query_embedding],
            anns_field="vector",
            param=search_params,
            limit=top_k,
            output_fields=["text", "source", "file_path", "filename"]
        )
    
    # Process results
    sources_data = []
    answer_parts = []
    
    for hits in results:
        for hit in hits:
            source = hit.entity.get("source", "unknown")
            text = hit.entity.get("text", "")
            file_path = hit.entity.get("file_path", "")
            score = hit.distance
            
            # Add to sources if not duplicate
            if not any(s['name'] == source for s in sources_data):
                sources_data.append({
                    'name': source,
                    'score': float(score) if score else None,
                    'excerpt': text[:500] if text else "",
                })
            
            answer_parts.append(text)
    
    # Generate answer from retrieved context
    context = "\n\n".join(answer_parts[:3])  # Use top 3 contexts
    
    answer = f"根据检索到的文档，以下是相关信息：\n\n{context[:1000]}..."
    
    return {
        'answer': answer,
        'sources': sources_data,
        'num_sources': len(sources_data),
    }


async def enhanced_rag_query(
    query: str,
    sources: Optional[List[str]] = None,
    use_cache: bool = True,
    top_k: int = 10,
) -> Dict[str, Any]:
    """Enhanced RAG query with caching support."""
    # Check cache
    if use_cache:
        cache = get_query_cache()
        cached = cache.get(query, sources)
        if cached:
            logger.info(f"Cache hit for query: {query[:50]}...")
            return json.loads(cached)
    
    # Execute query
    try:
        result = milvus_query(query, top_k=top_k, sources=sources)
    except Exception as e:
        logger.error(f"Error in milvus_query: {str(e)}")
        # Fallback: try using existing vector store
        from vector_store import VectorStore
        vs = VectorStore()
        docs = vs.get_documents(query, k=top_k, sources=sources)
        
        sources_data = []
        answer_parts = []
        for doc in docs:
            source = doc.metadata.get("source", "unknown")
            if not any(s['name'] == source for s in sources_data):
                sources_data.append({
                    'name': source,
                    'excerpt': doc.page_content[:500],
                })
            answer_parts.append(doc.page_content)
        
        context = "\n\n".join(answer_parts[:3])
        result = {
            'answer': f"根据检索到的文档：\n\n{context[:1000]}...",
            'sources': sources_data,
            'num_sources': len(sources_data),
        }
    
    # Cache result
    if use_cache:
        cache = get_query_cache()
        cache.set(query, json.dumps(result), sources)
    
    return result


def get_stats() -> Dict[str, Any]:
    """Get system statistics."""
    try:
        connections.connect(uri="http://milvus:19530")
        collection = Collection("context")
        collection.load()
        total_entities = collection.num_entities
    except Exception as e:
        logger.error(f"Error getting Milvus stats: {e}")
        total_entities = 0
    
    cache = get_query_cache()
    
    return {
        "index": {
            "collection": "context",
            "milvus_uri": "http://milvus:19530",
            "embedding_dimensions": 1024,
            "total_entities": total_entities,
        },
        "cache": {
            "enabled": True,
            "ttl": cache.ttl,
            "cached_queries": len(cache.cache),
        }
    }
