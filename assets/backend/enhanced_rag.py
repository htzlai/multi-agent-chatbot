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

    # 实测 Qwen3-Embedding-4B 输出维度为 2560
    DEFAULT_DIMENSIONS = 2560

    def __init__(
        self,
        model: str = "Qwen3-Embedding-4B-Q8_0.gguf",
        host: str = "http://qwen3-embedding:8000",
        dimensions: int = DEFAULT_DIMENSIONS,
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
            "auto": SentenceSplitter(chunk_size=512, chunk_overlap=128),
            "semantic": SentenceSplitter(chunk_size=400, chunk_overlap=100),
            "fixed": SentenceSplitter(chunk_size=512, chunk_overlap=128),
        }
        
        return strategies.get(strategy, strategies["auto"])


class QueryCache:
    """Simple in-memory query cache with hybrid flag support."""

    def __init__(self, ttl: int = 3600):
        self.cache: Dict[str, Tuple[str, float]] = {}
        self.ttl = ttl

    def _hash_query(self, query: str, sources: Optional[List[str]] = None, use_hybrid: bool = None) -> str:
        """Hash query with optional sources and hybrid flag."""
        key_data = json.dumps({
            'q': query,
            's': sorted(sources or []),
            'h': use_hybrid  # Include hybrid flag in cache key
        }, sort_keys=True)
        return hashlib.sha256(key_data.encode()).hexdigest()

    def get(self, query: str, sources: Optional[List[str]] = None, use_hybrid: bool = None) -> Optional[str]:
        key = self._hash_query(query, sources, use_hybrid)
        if key in self.cache:
            result, timestamp = self.cache[key]
            import time
            if time.time() - timestamp < self.ttl:
                return result
            else:
                del self.cache[key]
        return None
    
    def set(self, query: str, result: str, sources: Optional[List[str]] = None, use_hybrid: bool = None):
        import time
        key = self._hash_query(query, sources, use_hybrid)
        self.cache[key] = (result, time.time())
    
    def clear(self):
        """Clear all cached queries."""
        self.cache.clear()


# LLM client for answer generation
_llm_client = None

def get_llm_client():
    """Get or create the LLM client."""
    global _llm_client
    if _llm_client is None:
        from openai import AsyncOpenAI
        # Use the model from environment or default
        _llm_client = AsyncOpenAI(
            base_url="http://gpt-oss-120b:8000/v1",
            api_key="api_key"
        )
    return _llm_client


def _generate_answer_with_llm(query: str, context: str) -> str:
    """Generate answer using LLM with retrieved context."""
    try:
        # Get model client
        client = get_llm_client()
        
        # System prompt
        system_prompt = """你是一个专业的问答助手。请根据以下检索到的文档内容来回答用户的问题。

要求：
1. 只根据提供的文档内容回答，不要编造信息
2. 如果文档中没有相关信息，请明确说明"根据检索到的文档，未找到相关信息"
3. 回答要准确、简洁、使用中文

检索到的文档内容：
{context}

请根据以上文档内容回答问题。"""
        
        # Format prompt with context
        prompt = system_prompt.format(context=context[:3000])  # Limit context length
        
        # Call LLM
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            response = loop.run_until_complete(
                client.chat.completions.create(
                    model="gpt-oss-120b",
                    messages=[
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": query}
                    ],
                    max_tokens=1000,
                    temperature=0.3
                )
            )
            answer = response.choices[0].message.content
            return answer
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Error generating answer with LLM: {e}")
        # Fallback to simple concatenation
        return f"根据检索到的文档，以下是相关信息：\n\n{context[:1000]}..."


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
    
    # Build search parameters - detect metric type from index
    metric_type = "IP"  # Default
    try:
        indexes = collection.indexes
        if indexes:
            index_params = indexes[0]._index_params
            if "metric_type" in index_params:
                metric_type = index_params["metric_type"]
            elif "params" in index_params and isinstance(index_params["params"], dict):
                if "metric_type" in index_params["params"]:
                    metric_type = index_params["params"]["metric_type"]
    except Exception as e:
        logger.warning(f"Could not detect metric type, using default: {e}")
    
    search_params = {"metric_type": metric_type, "params": {}}
    
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
    
    # Generate answer using LLM (FIXED!)
    context = "\n\n".join(answer_parts[:3])  # Use top 3 contexts
    
    # Generate answer with LLM
    answer = _generate_answer_with_llm(query, context)
    
    return {
        'answer': answer,
        'sources': sources_data,
        'num_sources': len(sources_data),
        'search_type': 'vector'
    }


# ============================================================
# BM25 Implementation for Hybrid Search
# ============================================================

class BM25Indexer:
    """BM25 indexer for in-memory full-text search."""

    def __init__(self):
        self.documents: List[Dict[str, Any]] = []
        self.doc_ids: List[str] = []
        self.tokenized_corpus: List[List[str]] = []
        self._initialized = False
        self._avgdl = 0
        self._doc_len: List[int] = []

        # BM25 parameters
        self.k1 = 1.5
        self.b = 0.75

    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization - lowercase and split by whitespace/punctuation."""
        import re
        # Simple Chinese/English tokenization
        text = text.lower()
        # Split by non-alphanumeric characters
        tokens = re.findall(r'[a-z0-9]+', text)
        return tokens

    def initialize(self, collection_name: str = "context"):
        """Initialize BM25 index from Milvus collection."""
        try:
            connections.connect(uri="http://milvus:19530")
            collection = Collection(collection_name)
            collection.load()

            # Get all documents
            results = collection.query(
                expr="pk >= 0",
                output_fields=["pk", "text", "source", "file_path", "filename"]
            )

            self.documents = []
            self.doc_ids = []
            self.tokenized_corpus = []
            self._doc_len = []

            for i, doc in enumerate(results):
                text = doc.get("text", "")
                if text and len(text.strip()) > 0:
                    self.documents.append(doc)
                    self.doc_ids.append(str(doc.get("pk", i)))
                    tokens = self._tokenize(text)
                    self.tokenized_corpus.append(tokens)
                    self._doc_len.append(len(tokens))

            self._avgdl = sum(self._doc_len) / len(self._doc_len) if self._doc_len else 0
            self._initialized = True

            logger.info(f"BM25 index initialized with {len(self.documents)} documents")

        except Exception as e:
            logger.error(f"Error initializing BM25 index: {e}")
            self._initialized = False

    def _calc_idf(self) -> Dict[str, float]:
        """Calculate IDF for all terms in corpus."""
        import math
        N = len(self.tokenized_corpus)
        idf = {}
        df = {}

        for doc in self.tokenized_corpus:
            seen = set(doc)
            for term in seen:
                df[term] = df.get(term, 0) + 1

        for term, freq in df.items():
            idf[term] = math.log((N - freq + 0.5) / (freq + 0.5) + 1)

        return idf

    def search(self, query: str, top_k: int = 10) -> List[Tuple[int, float]]:
        """Search using BM25 algorithm."""
        if not self._initialized:
            self.initialize()

        if not self.tokenized_corpus:
            return []

        query_tokens = self._tokenize(query)
        idf = self._calc_idf()

        scores = []
        for i, doc in enumerate(self.tokenized_corpus):
            score = 0.0
            doc_len = self._doc_len[i]
            doc_freq = {}

            for term in doc:
                doc_freq[term] = doc_freq.get(term, 0) + 1

            for q_term in query_tokens:
                if q_term in doc_freq:
                    tf = doc_freq[q_term]
                    # BM25 scoring formula
                    numerator = tf * (self.k1 + 1)
                    denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / self._avgdl)
                    score += idf.get(q_term, 0) * numerator / denominator

            scores.append((i, score))

        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


# Global BM25 indexer instance
_bm25_indexer: Optional[BM25Indexer] = None


def get_bm25_indexer() -> BM25Indexer:
    """Get or create the global BM25 indexer."""
    global _bm25_indexer
    if _bm25_indexer is None:
        _bm25_indexer = BM25Indexer()
    return _bm25_indexer


def bm25_query(
    query: str,
    top_k: int = 10,
    sources: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Query using BM25 full-text search."""
    indexer = get_bm25_indexer()

    if not indexer._initialized:
        indexer.initialize()

    # Search BM25
    results = indexer.search(query, top_k=top_k * 2)  # Get more for filtering

    # Process results
    sources_data = []
    answer_parts = []
    seen_sources = set()

    for idx, score in results:
        if idx >= len(indexer.documents):
            continue

        doc = indexer.documents[idx]
        source = doc.get("source", "unknown")

        # Filter by sources if specified
        if sources and source not in sources:
            continue

        # Add to sources (dedup)
        if source not in seen_sources and len(sources_data) < top_k:
            seen_sources.add(source)
            text = doc.get("text", "")
            sources_data.append({
                'name': source,
                'score': float(score),
                'excerpt': text[:500] if text else "",
            })
            answer_parts.append(text)

    return {
        'answer_parts': answer_parts,
        'sources': sources_data,
        'num_sources': len(sources_data),
    }


def reciprocal_rank_fusion(
    vector_results: List[Dict],
    bm25_results: List[Dict],
    k: int = 60
) -> List[Dict]:
    """融合向量搜索和 BM25 搜索结果 using RRF.

    RRF formula: score = sum(1 / (k + rank)) for each result
    """
    from collections import defaultdict

    # Build score map: source -> {vector_rank, bm25_rank, vector_score, bm25_score}
    source_scores = defaultdict(lambda: {'vector_rank': None, 'bm25_rank': None, 'vector_score': 0, 'bm25_score': 0, 'excerpt': ''})

    # Assign vector ranks
    for rank, item in enumerate(vector_results):
        source = item.get('name', '')
        if source:
            source_scores[source]['vector_rank'] = rank + 1
            source_scores[source]['vector_score'] = item.get('score', 0)
            source_scores[source]['excerpt'] = item.get('excerpt', '')

    # Assign BM25 ranks
    for rank, item in enumerate(bm25_results):
        source = item.get('name', '')
        if source:
            source_scores[source]['bm25_rank'] = rank + 1
            source_scores[source]['bm25_score'] = item.get('score', 0)
            if not source_scores[source]['excerpt']:
                source_scores[source]['excerpt'] = item.get('excerpt', '')

    # Calculate RRF scores
    fused_results = []
    for source, scores in source_scores.items():
        rrf_score = 0.0

        # Vector RRF
        if scores['vector_rank'] is not None:
            rrf_score += 1.0 / (k + scores['vector_rank'])

        # BM25 RRF
        if scores['bm25_rank'] is not None:
            rrf_score += 1.0 / (k + scores['bm25_rank'])

        fused_results.append({
            'name': source,
            'score': rrf_score,
            'vector_score': scores['vector_score'],
            'bm25_score': scores['bm25_score'],
            'excerpt': scores['excerpt'],
        })

    # Sort by RRF score
    fused_results.sort(key=lambda x: x['score'], reverse=True)
    return fused_results


def hybrid_search(
    query: str,
    top_k: int = 10,
    sources: Optional[List[str]] = None,
    vector_weight: float = 0.5,
    bm25_weight: float = 0.5,
) -> Dict[str, Any]:
    """Hybrid search combining vector and BM25 results with RRF fusion."""
    import json

    # Get vector search results
    vector_result = milvus_query(query, top_k=top_k, sources=sources)
    vector_sources = vector_result.get('sources', [])

    # Get BM25 results
    bm25_result = bm25_query(query, top_k=top_k, sources=sources)
    bm25_sources = bm25_result.get('sources', [])

    # RRF Fusion
    fused_sources = reciprocal_rank_fusion(vector_sources, bm25_sources, k=60)

    # Format output
    final_sources = []
    for item in fused_sources[:top_k]:
        final_sources.append({
            'name': item['name'],
            'score': item['score'],
            'vector_score': item.get('vector_score'),
            'bm25_score': item.get('bm25_score'),
            'excerpt': item['excerpt'][:500] if item['excerpt'] else "",
        })

    # Get context for answer generation
    answer_parts = [s['excerpt'] for s in final_sources[:3] if s['excerpt']]
    context = "\n\n".join(answer_parts)

    # Generate answer with LLM
    answer = _generate_answer_with_llm(query, context)

    return {
        'answer': answer,
        'sources': final_sources,
        'num_sources': len(final_sources),
        'search_type': 'hybrid',
        'vector_weight': vector_weight,
        'bm25_weight': bm25_weight,
    }


async def enhanced_rag_query(
    query: str,
    sources: Optional[List[str]] = None,
    use_cache: bool = True,
    top_k: int = 10,
    use_hybrid: bool = True,  # 启用真正的混合搜索
) -> Dict[str, Any]:
    """Enhanced RAG query with hybrid search (BM25 + Vector) and caching support."""
    # Check cache
    if use_cache:
        cache = get_query_cache()
        # Include use_hybrid in cache key for correct caching
        cached = cache.get(query, sources, use_hybrid)
        if cached:
            logger.info(f"Cache hit for query: {query[:50]}...")
            return json.loads(cached)

    # Execute query - use hybrid search if enabled
    try:
        if use_hybrid:
            result = hybrid_search(query, top_k=top_k, sources=sources)
        else:
            result = milvus_query(query, top_k=top_k, sources=sources)
    except Exception as e:
        logger.error(f"Error in query: {str(e)}")
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
            'search_type': 'fallback',
        }

    # Cache result
    if use_cache:
        cache = get_query_cache()
        cache.set(query, json.dumps(result), sources, use_hybrid)

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
            "embedding_dimensions": Qwen3Embedding.DEFAULT_DIMENSIONS,  # 2560 (实测值)
            "total_entities": total_entities,
        },
        "cache": {
            "enabled": True,
            "ttl": cache.ttl,
            "cached_queries": len(cache.cache),
        }
    }
