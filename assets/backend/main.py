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
"""FastAPI backend — app creation, lifespan, middleware, router registration."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from agent import ChatAgent
from dependencies.providers import get_config_manager, get_postgres_storage
from errors import APIError, ErrorCode
from logger import logger
from openai_compatible import router as openai_router
from routers import register_routers
from services.vector_store_service import create_vector_store_with_config

# Rate limiting (optional)
try:
    from slowapi import Limiter
    from slowapi.errors import RateLimitExceeded
    from slowapi.util import get_remote_address

    RATE_LIMIT_AVAILABLE = True
except ImportError:
    RATE_LIMIT_AVAILABLE = False


# ------------------------------------------------------------------
# Lifespan
# ------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize shared resources on startup, tear down on shutdown."""
    config_manager = get_config_manager()
    postgres_storage = get_postgres_storage()
    vector_store = create_vector_store_with_config(config_manager)
    vector_store._initialize_store()

    logger.debug("Initializing PostgreSQL storage and agent...")
    try:
        await postgres_storage.init_pool()
        logger.info("PostgreSQL storage initialized successfully")

        agent = await ChatAgent.create(
            vector_store=vector_store,
            config_manager=config_manager,
            postgres_storage=postgres_storage,
        )
        logger.info("ChatAgent initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize: {e}")
        raise

    # Attach to app.state so providers can access them
    app.state.agent = agent
    app.state.vector_store = vector_store

    yield

    try:
        await postgres_storage.close()
        logger.debug("PostgreSQL storage closed successfully")
    except Exception as e:
        logger.error(f"Error closing PostgreSQL storage: {e}")


# ------------------------------------------------------------------
# App
# ------------------------------------------------------------------

app = FastAPI(
    title="Chatbot API",
    description="Backend API for LLM-powered chatbot with RAG capabilities",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3010",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3010",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------
# Exception handlers — unified error envelope
# ------------------------------------------------------------------

@app.exception_handler(APIError)
async def api_error_handler(request, exc: APIError):
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    validation_errors = [
        {
            "field": ".".join(str(x) for x in err.get("loc", [])),
            "message": err.get("msg", ""),
            "type": err.get("type", ""),
        }
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": ErrorCode.VALIDATION_ERROR,
                "message": "Request validation failed",
                "details": {"validation_errors": validation_errors},
            }
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)

    if isinstance(exc.detail, list):
        validation_errors = [
            {
                "field": ".".join(str(x) for x in err.get("loc", [])),
                "message": err.get("msg", ""),
                "type": err.get("type", ""),
            }
            for err in exc.detail
            if isinstance(err, dict)
        ]
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": ErrorCode.VALIDATION_ERROR,
                    "message": "Request validation failed",
                    "details": {"validation_errors": validation_errors},
                }
            },
        )

    error_code = ErrorCode.UNKNOWN_ERROR
    if exc.status_code == 401:
        error_code = ErrorCode.UNAUTHORIZED
    elif exc.status_code == 403:
        error_code = ErrorCode.FORBIDDEN
    elif exc.status_code == 404:
        error_code = ErrorCode.NOT_FOUND

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": error_code,
                "message": str(exc.detail) if exc.detail else "Unknown error",
                "details": {},
            }
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": ErrorCode.INTERNAL_ERROR,
                "message": "An internal error occurred",
                "details": {"type": type(exc).__name__},
            }
        },
    )


if RATE_LIMIT_AVAILABLE:
    limiter = Limiter(key_func=get_remote_address)

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request, exc):
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many requests, please try again later",
                    "details": {"retry_after": str(exc)},
                }
            },
        )


# ------------------------------------------------------------------
# Router registration
# ------------------------------------------------------------------

register_routers(app)
app.include_router(openai_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
