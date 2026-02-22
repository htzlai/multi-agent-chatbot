"""
OpenAI 兼容 API 模块

提供标准 OpenAI API 端点，兼容 LobeHub、LangChain 等前端
"""

from .models import (
    ChatCompletionRequest,
    ChatCompletion,
    ChatCompletionChunk,
    EmbeddingsRequest,
    Embedding,
    Model,
    ModelList,
    UsageInfo,
)
from .router import router

__all__ = [
    "ChatCompletionRequest",
    "ChatCompletion",
    "ChatCompletionChunk",
    "EmbeddingsRequest",
    "Embedding",
    "Model",
    "ModelList",
    "UsageInfo",
    "router",
]
