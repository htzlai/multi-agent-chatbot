# SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Centralized Milvus client.

Every pymilvus interaction in the project MUST go through this module.
No router, service, or RAG module should import ``pymilvus`` directly.
"""

import logging
from typing import Any, Dict, List, Optional

from pymilvus import Collection, MilvusException, connections, utility

logger = logging.getLogger(__name__)

# Default connection parameters
_MILVUS_URI = "http://milvus:19530"
_DEFAULT_COLLECTION = "context"


def get_connection(uri: str = _MILVUS_URI, alias: str = "default") -> None:
    """Ensure a Milvus connection is established (idempotent)."""
    try:
        connections.connect(alias=alias, uri=uri)
    except MilvusException as exc:
        logger.error({"message": "Milvus connection failed", "uri": uri, "error": str(exc)})
        raise


def get_collection(name: str = _DEFAULT_COLLECTION, *, load: bool = True) -> Collection:
    """Return a ``Collection`` handle, optionally loading it into memory."""
    get_connection()
    collection = Collection(name)
    if load:
        collection.load()
    return collection


def get_vector_counts(collection_name: str = _DEFAULT_COLLECTION) -> Dict[str, Any]:
    """Return entity count and basic stats for a collection."""
    get_connection()
    if not utility.has_collection(collection_name):
        return {"exists": False, "count": 0}
    col = Collection(collection_name)
    col.load()
    return {
        "exists": True,
        "count": col.num_entities,
        "name": collection_name,
    }


def health_check(uri: str = _MILVUS_URI) -> Dict[str, str]:
    """Check Milvus connectivity and collection availability."""
    try:
        connections.connect(uri=uri)
        if utility.has_collection(_DEFAULT_COLLECTION):
            col = Collection(_DEFAULT_COLLECTION)
            col.load()
            return {"status": "healthy"}
        return {"status": "no_collection"}
    except Exception as exc:
        return {"status": f"unhealthy: {str(exc)[:80]}"}


def list_collections() -> List[str]:
    """Return all collection names in the connected Milvus instance."""
    get_connection()
    return utility.list_collections()


def drop_collection(name: str) -> bool:
    """Drop a collection by name. Returns True if it existed."""
    get_connection()
    if utility.has_collection(name):
        utility.drop_collection(name)
        return True
    return False


def query_source_counts(
    sources: List[str], collection_name: str = _DEFAULT_COLLECTION
) -> Dict[str, int]:
    """Return vector count per source name in the collection."""
    get_connection()
    if not utility.has_collection(collection_name):
        return {s: 0 for s in sources}
    col = Collection(collection_name)
    col.load()
    counts: Dict[str, int] = {}
    for source in sources:
        try:
            result = col.query(expr=f'source == "{source}"', output_fields=["pk"])
            counts[source] = len(result)
        except Exception:
            counts[source] = 0
    return counts


def query_unique_sources(collection_name: str = _DEFAULT_COLLECTION) -> set:
    """Return the set of unique source names stored in the collection."""
    get_connection()
    if not utility.has_collection(collection_name):
        return set()
    col = Collection(collection_name)
    col.load()
    try:
        result = col.query(expr="pk >= 0", output_fields=["source"])
        return {item["source"] for item in result if "source" in item}
    except Exception:
        return set()


def get_collection_stats(collection_name: str = _DEFAULT_COLLECTION) -> Dict[str, Any]:
    """Return detailed collection statistics (entities, fields, indexes)."""
    get_connection()
    if not utility.has_collection(collection_name):
        return {
            "collection": collection_name,
            "total_entities": 0,
            "fields": [],
            "index_count": 0,
            "status": "not_initialized",
            "message": "Collection does not exist. Upload documents to initialize.",
        }
    col = Collection(collection_name)
    col.load()
    return {
        "collection": collection_name,
        "total_entities": col.num_entities,
        "fields": [{"name": f.name, "type": str(f.dtype)} for f in col.schema.fields],
        "field_names": [f.name for f in col.schema.fields],
        "index_count": len(col.indexes),
        "status": "ready" if col.num_entities > 0 else "empty",
    }


def detect_metric_type(collection_name: str = _DEFAULT_COLLECTION) -> str:
    """Detect the metric type from the first index of a collection."""
    col = get_collection(collection_name)
    try:
        indexes = col.indexes
        if indexes:
            params = indexes[0]._index_params
            if "metric_type" in params:
                return params["metric_type"]
    except Exception:
        pass
    return "IP"  # default fallback
