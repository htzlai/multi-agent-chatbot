# SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Router registration — include all routers on the FastAPI app."""

from fastapi import FastAPI

from routers.api_v1 import router as api_v1_router
from routers.chat_stream import router as chat_stream_router
from routers.health import router as health_router


def register_routers(app: FastAPI) -> None:
    """Include all routers on the given FastAPI application."""
    app.include_router(health_router)
    app.include_router(chat_stream_router)
    app.include_router(api_v1_router)
