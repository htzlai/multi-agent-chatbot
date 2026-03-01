# SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Async embedding client for Qwen3-Embedding.

Replaces the sync ``requests.post()`` in the original ``Qwen3Embedding``
with ``httpx.AsyncClient`` so it no longer blocks the event loop.
"""

import logging
from functools import lru_cache
from typing import List

import httpx

logger = logging.getLogger(__name__)

# Qwen3-Embedding-4B output dimensions
DEFAULT_DIMENSIONS = 2560


class AsyncQwen3Embedding:
    """Async Qwen3 embedding client compatible with LlamaIndex.

    Uses ``httpx.AsyncClient`` instead of sync ``requests`` to avoid
    blocking the FastAPI event loop.
    """

    def __init__(
        self,
        model: str = "Qwen3-Embedding-4B-Q8_0.gguf",
        host: str = "http://qwen3-embedding:8000",
        dimensions: int = DEFAULT_DIMENSIONS,
        timeout: float = 30.0,
    ):
        self.model = model
        self.url = f"{host}/v1/embeddings"
        self.dimensions = dimensions
        self._timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Embed a batch of texts asynchronously."""
        resp = await self._client.post(
            self.url,
            json={"input": texts, "model": self.model},
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        return [d["embedding"] for d in resp.json()["data"]]

    async def embed_single(self, text: str) -> List[float]:
        """Embed a single text string."""
        results = await self.embed([text])
        return results[0]

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()


@lru_cache()
def get_embedding_client() -> AsyncQwen3Embedding:
    """Return the shared ``AsyncQwen3Embedding`` singleton."""
    return AsyncQwen3Embedding()
