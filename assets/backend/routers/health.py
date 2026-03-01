# SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Health check, metrics, and debug endpoints — thin HTTP layer delegating to health_service."""

from fastapi import APIRouter, Depends

from dependencies.providers import get_config_manager, get_postgres_storage
from services import health_service, rag_service

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(
    storage=Depends(get_postgres_storage),
):
    """Global health check — verify all infrastructure status."""
    return await health_service.check_all_services(storage)


@router.get("/health/rag")
async def rag_health_check():
    """RAG system health check."""
    try:
        return health_service.get_rag_health()
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


@router.get("/metrics")
async def metrics(
    storage=Depends(get_postgres_storage),
):
    """System performance metrics."""
    try:
        return await health_service.get_metrics(storage)
    except Exception as e:
        return {"error": str(e)}


@router.get("/debug/config")
async def debug_config(
    config=Depends(get_config_manager),
):
    """Debug endpoint — view current config (dev only)."""
    try:
        cfg = config.read_config()
        return {
            "sources_count": len(cfg.sources),
            "selected_sources_count": len(cfg.selected_sources or []),
            "current_model": cfg.get_selected_model(),
            "current_chat_id": cfg.current_chat_id,
        }
    except Exception as e:
        return {"error": str(e)}


@router.post("/debug/rebuild-bm25")
async def rebuild_bm25_index():
    """Rebuild BM25 index."""
    return rag_service.rebuild_bm25()
