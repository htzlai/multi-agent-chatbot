# SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Langfuse observability — client lifecycle and flush helpers."""

import os
from typing import Optional

from logger import logger

_langfuse_client: Optional["Langfuse"] = None


def get_langfuse_client() -> Optional["Langfuse"]:
    """Return the Langfuse client if configured, else None.

    Uses LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, and optionally
    LANGFUSE_BASE_URL (for self-hosted). If keys are not set, returns None
    so the application runs without observability.
    """
    global _langfuse_client

    if _langfuse_client is not None:
        return _langfuse_client

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
    secret_key = os.getenv("LANGFUSE_SECRET_KEY", "").strip()

    if not public_key or not secret_key:
        logger.debug("Langfuse not configured: LANGFUSE_PUBLIC_KEY or LANGFUSE_SECRET_KEY missing")
        return None

    try:
        from langfuse import Langfuse

        base_url = os.getenv("LANGFUSE_BASE_URL", "").strip()
        _langfuse_client = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=base_url if base_url else None,
        )
        logger.debug("Langfuse client initialized successfully")
        return _langfuse_client
    except Exception as e:
        logger.warning(f"Failed to initialize Langfuse client: {e}")
        return None


def flush_langfuse():
    """Flush pending Langfuse events. Call before process exit if needed."""
    global _langfuse_client
    if _langfuse_client is not None:
        try:
            _langfuse_client.flush()
        except Exception as e:
            logger.debug(f"Langfuse flush failed: {e}")
