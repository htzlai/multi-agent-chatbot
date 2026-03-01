"""
OpenAI 兼容 API 路由 - 正确的反向代理架构

直接代理请求到模型服务:
- /v1/chat/completions → gpt-oss-120b:8000
- /v1/embeddings → qwen3-embedding:8000
- /v1/models → 聚合两个服务
"""

import asyncio
import json
import time
import uuid
from typing import AsyncGenerator, Dict, List, Optional, Union

import httpx
from fastapi import APIRouter, BackgroundTasks, Request

from errors import APIError, ErrorCode, InternalError, NotFoundError
from fastapi.responses import StreamingResponse

from .models import (
    ChatCompletion,
    ChatCompletionChunk,
    ChatCompletionRequest,
    EmbeddingsRequest,
    Embedding,
    EmbeddingData,
    Model,
    ModelList,
    UsageInfo,
)

router = APIRouter(prefix="/v1")

# 模型服务地址
LLM_BASE_URL = "http://gpt-oss-120b:8000/v1"
EMBEDDING_BASE_URL = "http://qwen3-embedding:8000/v1"


# ============================================================
# 辅助函数
# ============================================================

def generate_id() -> str:
    """生成唯一 ID"""
    return f"chatcmpl-{uuid.uuid4().hex[:8]}"


def get_timestamp() -> int:
    """获取当前时间戳"""
    return int(time.time())


# ============================================================
# GET /v1/models - 模型列表 (聚合)
# ============================================================

@router.get("/models", response_model=ModelList)
async def list_models():
    """
    获取可用模型列表 - 聚合两个模型服务
    """
    models = []
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        # 获取 LLM 模型
        try:
            response = await client.get(f"{LLM_BASE_URL}/models")
            if response.status_code == 200:
                data = response.json()
                for model in data.get("data", []):
                    models.append(Model(
                        id=model["id"],
                        object="model",
                        created=model.get("created", get_timestamp()),
                        owned_by=model.get("owned_by", "local")
                    ))
        except Exception as e:
            print(f"Error fetching LLM models: {e}")
        
        # 获取嵌入模型
        try:
            response = await client.get(f"{EMBEDDING_BASE_URL}/models")
            if response.status_code == 200:
                data = response.json()
                for model in data.get("data", []):
                    models.append(Model(
                        id=model["id"],
                        object="model",
                        created=model.get("created", get_timestamp()),
                        owned_by=model.get("owned_by", "local")
                    ))
        except Exception as e:
            print(f"Error fetching embedding models: {e}")
    
    # 如果没有获取到任何模型，返回默认列表
    if not models:
        models = [
            Model(id="gpt-oss-120b", object="model", created=get_timestamp(), owned_by="local"),
            Model(id="qwen3-embedding", object="model", created=get_timestamp(), owned_by="local"),
        ]
    
    return ModelList(data=models)


@router.get("/models/{model_id}", response_model=Model)
async def get_model(model_id: str):
    """获取特定模型信息"""
    models_response = await list_models()
    for model in models_response.data:
        if model.id == model_id:
            return model
    raise NotFoundError("Model", model_id)


# ============================================================
# POST /v1/chat/completions - 聊天完成 (代理)
# ============================================================

@router.post("/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    background_tasks: BackgroundTasks,
    req: Request
):
    """
    聊天完成 - 直接代理到 gpt-oss-120b 服务
    支持流式和非流式
    """
    if request.stream:
        return StreamingResponse(
            stream_chat_completions(request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )
    else:
        return await non_stream_chat_completions(request)


async def non_stream_chat_completions(request: ChatCompletionRequest) -> ChatCompletion:
    """非流式聊天完成 - 直接代理"""
    async with httpx.AsyncClient(timeout=300.0) as client:
        # 构建请求体
        payload = {
            "model": request.model,
            "messages": [
                {"role": msg.role.value if hasattr(msg.role, 'value') else msg.role, "content": msg.content}
                for msg in request.messages
            ],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": False
        }
        
        # 处理工具调用
        if request.tools:
            payload["tools"] = request.tools
            if request.tool_choice:
                payload["tool_choice"] = request.tool_choice
        
        try:
            response = await client.post(
                f"{LLM_BASE_URL}/chat/completions",
                json=payload
            )
            
            if response.status_code == 200:
                data = response.json()
                return ChatCompletion(
                    id=data.get("id", generate_id()),
                    object="chat.completion",
                    created=data.get("created", get_timestamp()),
                    model=data.get("model", request.model),
                    choices=data.get("choices", []),
                    usage=data.get("usage", UsageInfo())
                )
            else:
                raise APIError(
                    code=ErrorCode.INTERNAL_ERROR,
                    message=f"LLM service error: {response.text}",
                    status_code=response.status_code,
                )
        except httpx.TimeoutException:
            raise APIError(code=ErrorCode.INTERNAL_ERROR, message="LLM service timeout", status_code=504)
        except Exception as e:
            raise InternalError(f"Error calling LLM: {str(e)}")


async def stream_chat_completions(request: ChatCompletionRequest) -> AsyncGenerator[str, None]:
    """流式聊天完成 - 直接代理"""
    # 构建请求体
    payload = {
        "model": request.model,
        "messages": [
            {"role": msg.role.value if hasattr(msg.role, 'value') else msg.role, "content": msg.content}
            for msg in request.messages
        ],
        "temperature": request.temperature,
        "max_tokens": request.max_tokens,
        "stream": True
    }
    
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream(
                "POST",
                f"{LLM_BASE_URL}/chat/completions",
                json=payload
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        yield line + "\n\n"
                        if line == "data: [DONE]":
                            break
    except Exception as e:
        error_json = json.dumps({'error': {'message': str(e)}})
        yield f"data: {error_json}\n\n"
        yield "data: [DONE]\n\n"


# ============================================================
# POST /v1/embeddings - 嵌入 (代理)
# ============================================================

@router.post("/embeddings", response_model=Embedding)
async def create_embeddings(request: EmbeddingsRequest):
    """创建嵌入 - 直接代理到 qwen3-embedding 服务"""
    
    # 确定使用的模型
    model = request.model
    if not model or model == "embedding":
        model = "qwen3-embedding"
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        payload = {
            "model": model,
            "input": request.input
        }
        
        try:
            response = await client.post(
                f"{EMBEDDING_BASE_URL}/embeddings",
                json=payload
            )
            
            if response.status_code == 200:
                data = response.json()
                return Embedding(
                    object="list",
                    data=data.get("data", []),
                    model=data.get("model", model),
                    usage=data.get("usage", UsageInfo())
                )
            else:
                raise APIError(
                    code=ErrorCode.INTERNAL_ERROR,
                    message=f"Embedding service error: {response.text}",
                    status_code=response.status_code,
                )
        except httpx.TimeoutException:
            raise APIError(code=ErrorCode.INTERNAL_ERROR, message="Embedding service timeout", status_code=504)
        except Exception as e:
            raise InternalError(f"Error calling embedding service: {str(e)}")
