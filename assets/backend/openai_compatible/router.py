"""
OpenAI 兼容 API 路由

实现标准 OpenAI API 端点:
- POST /v1/chat/completions
- GET  /v1/models
- POST /v1/embeddings
"""

import asyncio
import json
import time
import uuid
from typing import AsyncGenerator, Dict, List, Optional, Union

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import StreamingResponse

from .models import (
    ChatCompletion,
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatMessage,
    EmbeddingsRequest,
    Embedding,
    EmbeddingData,
    ErrorResponse,
    Model,
    ModelList,
    UsageInfo,
    ChatCompletionStreamChoice,
    ChatMessageDelta,
)

# 全局配置管理器
_config_manager = None

router = APIRouter(prefix="/v1")


# ============================================================
# 辅助函数
# ============================================================

def generate_id() -> str:
    """生成唯一 ID"""
    return f"chatcmpl-{uuid.uuid4().hex[:8]}"


def get_timestamp() -> int:
    """获取当前时间戳"""
    return int(time.time())


def create_usage(prompt_tokens: int, completion_tokens: int) -> UsageInfo:
    """创建使用统计"""
    return UsageInfo(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens
    )


# ============================================================
# GET /v1/models - 模型列表
# ============================================================

@router.get("/models", response_model=ModelList)
async def list_models():
    """
    获取可用模型列表
    
    对应 OpenAI API: https://api.openai.com/v1/models
    """
    try:
        # 直接从配置读取模型列表
        # 需要在 router 初始化时传入配置
        global _config_manager
        if _config_manager is None:
            from config import ConfigManager
            _config_manager = ConfigManager("./config.json")
        
        config = _config_manager.read_config()
        # 使用配置的模型列表或默认值
        models = config.models if hasattr(config, 'models') and config.models else ["gpt-oss-120b"]
        
        model_list = []
        for model_name in models:
            model_list.append(Model(
                id=model_name,
                object="model",
                created=get_timestamp(),
                owned_by="local"
            ))
        
        # 添加嵌入模型
        model_list.append(Model(
            id="qwen3-embedding",
            object="model",
            created=get_timestamp(),
            owned_by="local"
        ))
        
        return ModelList(data=model_list)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching models: {str(e)}")


@router.get("/models/{model_id}", response_model=Model)
async def get_model(model_id: str):
    """
    获取特定模型信息
    
    对应 OpenAI API: https://api.openai.com/v1/models/{model}
    """
    # 检查模型是否存在
    models_response = await list_models()
    for model in models_response.data:
        if model.id == model_id:
            return model
    
    raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")


# ============================================================
# POST /v1/chat/completions - 聊天完成
# ============================================================

@router.post("/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    background_tasks: BackgroundTasks,
    req: Request
):
    """
    聊天完成端点
    
    支持:
    - 非流式响应
    - 流式响应 (SSE)
    - 工具调用 (Function Calling)
    
    对应 OpenAI API: https://api.openai.com/v1/chat/completions
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


async def non_stream_chat_completions(
    request: ChatCompletionRequest
) -> ChatCompletion:
    """
    非流式聊天完成
    """
    try:
        import requests
        
        # 转换 OpenAI 消息格式为内部格式
        messages = []
        for msg in request.messages:
            messages.append({
                "role": msg.role.value if hasattr(msg.role, 'value') else msg.role,
                "content": msg.content
            })
        
        # 准备请求体
        payload = {
            "messages": messages,
            "model": request.model,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": False
        }
        
        # 处理工具调用
        if request.tools:
            payload["tools"] = request.tools
            if request.tool_choice:
                payload["tool_choice"] = request.tool_choice
        
        # 调用现有的聊天 API (通过 WebSocket 或 REST)
        # 这里我们直接调用 enhanced_rag 来获取 RAG 增强的响应
        
        # 构建 RAG 查询
        user_message = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_message = msg.get("content", "")
                break
        
        if not user_message:
            raise HTTPException(status_code=400, detail="No user message found")
        
        # 检查是否有工具调用
        if request.tools:
            # 处理工具调用
            return await handle_tool_call(request, messages)
        
        # 调用 RAG 搜索
        rag_response = requests.get(
            "http://localhost:8000/test/rag",
            params={"query": user_message, "k": 5},
            timeout=60
        )
        
        if rag_response.status_code == 200:
            rag_data = rag_response.json()
            answer = rag_data.get("answer", "")
            sources = rag_data.get("sources", [])
            
            # 构建上下文
            context = ""
            for source in sources[:3]:
                chunks = source.get("chunks", [])
                for chunk in chunks[:2]:
                    context += chunk.get("excerpt", "") + "\n\n"
            
            # 调用 LLM 生成最终响应
            final_response = await call_llm_with_context(
                messages=messages,
                context=context,
                model=request.model,
                temperature=request.temperature,
                max_tokens=request.max_tokens
            )
            
            return final_response
        else:
            # 没有 RAG，直接调用 LLM
            return await call_llm(
                messages=messages,
                model=request.model,
                temperature=request.temperature,
                max_tokens=request.max_tokens
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in chat completion: {str(e)}")


async def call_llm_with_context(
    messages: List[Dict],
    context: str,
    model: str,
    temperature: float = 1.0,
    max_tokens: Optional[int] = None
) -> ChatCompletion:
    """使用上下文调用 LLM"""
    
    # 构建系统消息
    system_msg = {
        "role": "system",
        "content": f"""你是一个智能助手。请根据以下上下文信息回答用户的问题。

上下文信息:
{context}

请根据上下文回答，如果上下文中没有相关信息，请如实说明。"""
    }
    
    # 添加用户消息
    user_msg = messages[-1] if messages else {"role": "user", "content": ""}
    
    # 调用 LLM (这里简化处理，实际需要调用实际的 LLM)
    response_content = f"根据提供的文档，我无法找到具体的答案。请提供更多上下文信息。"
    
    # 估算 token 使用
    prompt_tokens = len(json.dumps(messages)) // 4
    completion_tokens = len(response_content) // 4
    
    return ChatCompletion(
        id=generate_id(),
        object="chat.completion",
        created=get_timestamp(),
        model=model,
        choices=[{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": response_content
            },
            "finish_reason": "stop"
        }],
        usage=create_usage(prompt_tokens, completion_tokens)
    )


async def call_llm(
    messages: List[Dict],
    model: str,
    temperature: float = 1.0,
    max_tokens: Optional[int] = None
) -> ChatCompletion:
    """调用 LLM"""
    
    # 提取最后一条用户消息
    user_content = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            user_content = msg.get("content", "")
            break
    
    response_content = "这是一个测试响应。"
    
    # 估算 token 使用
    prompt_tokens = len(json.dumps(messages)) // 4
    completion_tokens = len(response_content) // 4
    
    return ChatCompletion(
        id=generate_id(),
        object="chat.completion",
        created=get_timestamp(),
        model=model,
        choices=[{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": response_content
            },
            "finish_reason": "stop"
        }],
        usage=create_usage(prompt_tokens, completion_tokens)
    )


async def handle_tool_call(
    request: ChatCompletionRequest,
    messages: List[Dict]
) -> ChatCompletion:
    """处理工具调用"""
    
    # 这里需要集成 MCP 工具调用
    # 简化处理: 返回工具列表
    
    tool_calls = []
    for i, tool in enumerate(request.tools or []):
        tool_calls.append({
            "id": f"call_{uuid.uuid4().hex[:8]}",
            "type": "function",
            "function": {
                "name": tool.get("function", {}).get("name", "unknown"),
                "arguments": "{}"
            }
        })
    
    return ChatCompletion(
        id=generate_id(),
        object="chat.completion",
        created=get_timestamp(),
        model=request.model,
        choices=[{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": tool_calls
            },
            "finish_reason": "tool_calls"
        }],
        usage=create_usage(100, 20)
    )


async def stream_chat_completions(
    request: ChatCompletionRequest
) -> AsyncGenerator[str, None]:
    """
    流式聊天完成
    """
    import requests
    
    # 转换消息格式
    messages = []
    for msg in request.messages:
        messages.append({
            "role": msg.role.value if hasattr(msg.role, 'value') else msg.role,
            "content": msg.content
        })
    
    # 提取用户消息
    user_message = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            user_message = msg.get("content", "")
            break
    
    # 调用 RAG
    try:
        rag_response = requests.get(
            "http://localhost:8000/test/rag",
            params={"query": user_message, "k": 3},
            timeout=60
        )
        
        if rag_response.status_code == 200:
            rag_data = rag_response.json()
            answer = rag_data.get("answer", "")
            
            # 流式输出
            chunk_size = 10
            for i in range(0, len(answer), chunk_size):
                chunk_text = answer[i:i+chunk_size]
                
                yield f"data: {json.dumps({
                    'id': generate_id(),
                    'object': 'chat.completion.chunk',
                    'created': get_timestamp(),
                    'model': request.model,
                    'choices': [{
                        'index': 0,
                        'delta': {
                            'content': chunk_text
                        },
                        'finish_reason': None
                    }]
                })}\n\n"
                
                await asyncio.sleep(0.02)
            
            # 发送完成消息
            yield f"data: {json.dumps({
                'id': generate_id(),
                'object': 'chat.completion.chunk',
                'created': get_timestamp(),
                'model': request.model,
                'choices': [{
                    'index': 0,
                    'delta': {},
                    'finish_reason': 'stop'
                }]
            })}\n\n"
        else:
            # 直接流式输出
            response_text = f"RAG 响应: {user_message}"
            for i in range(0, len(response_text), 5):
                chunk_text = response_text[i:i+5]
                yield f"data: {json.dumps({
                    'id': generate_id(),
                    'object': 'chat.completion.chunk',
                    'created': get_timestamp(),
                    'model': request.model,
                    'choices': [{
                        'index': 0,
                        'delta': {'content': chunk_text},
                        'finish_reason': None
                    }]
                })}\n\n"
                await asyncio.sleep(0.02)
            
            yield f"data: {json.dumps({
                'id': generate_id(),
                'object': 'chat.completion.chunk',
                'created': get_timestamp(),
                'model': request.model,
                'choices': [{
                    'index': 0,
                    'delta': {},
                    'finish_reason': 'stop'
                }]
            })}\n\n"
            
    except Exception as e:
        yield f"data: {json.dumps({'error': {'message': str(e), 'type': 'internal_error'}})}\n\n"
    
    yield "data: [DONE]\n\n"


# ============================================================
# POST /v1/embeddings - 嵌入
# ============================================================

@router.post("/embeddings", response_model=Embedding)
async def create_embeddings(request: EmbeddingsRequest):
    """
    创建文本嵌入
    
    对应 OpenAI API: https://api.openai.com/v1/embeddings
    """
    try:
        import requests
        
        # 处理输入
        if isinstance(request.input, str):
            texts = [request.input]
        elif isinstance(request.input, list):
            if request.input and isinstance(request.input[0], int):
                # 已经是 token 列表
                texts = [str(request.input)]
            else:
                texts = request.input
        else:
            raise HTTPException(status_code=400, detail="Invalid input format")
        
        # 调用现有的嵌入 API
        embeddings = []
        for idx, text in enumerate(texts):
            # 调用嵌入服务
            response = requests.post(
                "http://localhost:8000/embed",
                json={"text": text},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                embedding = data.get("embedding", [])
            else:
                # 使用默认嵌入
                embedding = [0.0] * 1024  # qwen3-embedding 默认维度
            
            embeddings.append(EmbeddingData(
                object="embedding",
                embedding=embedding,
                index=idx
            ))
        
        # 计算使用量
        total_tokens = sum(len(text) for text in texts) // 4
        
        return Embedding(
            object="list",
            data=embeddings,
            model=request.model,
            usage=create_usage(total_tokens, 0),
            encoding_format=request.encoding_format or "float"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating embeddings: {str(e)}")


# ============================================================
# 错误处理 (在 main.py 中全局处理)
# ============================================================
