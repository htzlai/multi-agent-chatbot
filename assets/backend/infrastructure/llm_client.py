# SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Singleton LLM client.

Wraps ``openai.AsyncOpenAI`` so that every caller shares one connection
pool instead of creating a new client (or worse, a new event-loop) per
request.
"""

import os
import logging
from functools import lru_cache

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# Environment-driven defaults
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://gpt-oss-120b:8000/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "api_key")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-oss-120b")


@lru_cache()
def get_llm_client() -> AsyncOpenAI:
    """Return the shared ``AsyncOpenAI`` singleton."""
    return AsyncOpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)


def get_llm_model() -> str:
    """Return the configured LLM model name."""
    return LLM_MODEL
