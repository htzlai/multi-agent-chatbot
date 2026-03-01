# SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Backward-compatible re-export shim.

All logic has moved to ``services.vector_store_service``.
This file exists only so that any stale imports still resolve.
It will be deleted once all callers are confirmed migrated.
"""

from services.vector_store_service import (  # noqa: F401
    CustomEmbeddings,
    VectorStore,
    create_vector_store_with_config,
)

__all__ = ["CustomEmbeddings", "VectorStore", "create_vector_store_with_config"]
