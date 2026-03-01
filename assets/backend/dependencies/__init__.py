# SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Dependency injection providers for FastAPI."""

from dependencies.providers import (
    get_agent,
    get_config_manager,
    get_postgres_storage,
    get_vector_store,
)

__all__ = [
    "get_agent",
    "get_config_manager",
    "get_postgres_storage",
    "get_vector_store",
]
