"""
OpenAI 兼容 API 数据模型定义

参考: https://platform.openai.com/docs/api-reference/chat
"""

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from enum import Enum


class ChatRole(str, Enum):
    """聊天角色"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    FUNCTION = "function"
    TOOL = "tool"


class FunctionCall(str, Enum):
    """函数调用类型"""
    NONE = "none"
    AUTO = "auto"


# ============================================================
# 请求模型
# ============================================================


class ChatMessage(BaseModel):
    """聊天消息"""
    role: ChatRole
    content: Optional[str] = None
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


class FunctionDefinition(BaseModel):
    """函数定义"""
    name: str
    description: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None


class ChatFunction(BaseModel):
    """聊天函数"""
    name: Optional[str] = None
    description: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None


class ChatCompletionRequest(BaseModel):
    """聊天完成请求"""
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = Field(default=1.0, ge=0, le=2)
    top_p: Optional[float] = Field(default=1.0, ge=0, le=1)
    n: Optional[int] = Field(default=1, ge=1)
    stream: Optional[bool] = False
    stop: Optional[Union[str, List[str]]] = None
    max_tokens: Optional[int] = None
    presence_penalty: Optional[float] = Field(default=0, ge=-2, le=2)
    frequency_penalty: Optional[float] = Field(default=0, ge=-2, le=2)
    logit_bias: Optional[Dict[str, int]] = None
    user: Optional[str] = None
    functions: Optional[List[ChatFunction]] = None
    function_call: Optional[Union[str, FunctionCall]] = None
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None
    response_format: Optional[Dict[str, Any]] = None
    seed: Optional[int] = None
    stream_options: Optional[Dict[str, Any]] = None


class EmbeddingsRequest(BaseModel):
    """嵌入请求"""
    model: str
    input: Union[str, List[str], List[int], List[List[int]]]
    encoding_format: Optional[str] = "float"
    dimensions: Optional[int] = None
    user: Optional[str] = None


# ============================================================
# 响应模型
# ============================================================


class UsageInfo(BaseModel):
    """使用统计"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatMessageDelta(BaseModel):
    """聊天消息增量（流式响应）"""
    role: Optional[ChatRole] = None
    content: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


class ChatChoice(BaseModel):
    """聊天选项"""
    index: int
    message: Optional[ChatMessage] = None
    finish_reason: Optional[str] = None
    delta: Optional[ChatMessageDelta] = None
    logprobs: Optional[Dict[str, Any]] = None


class ChatCompletionChoice(BaseModel):
    """聊天完成选项（非流式）"""
    index: int
    message: ChatMessage
    finish_reason: Optional[str] = None


class ChatCompletionStreamChoice(BaseModel):
    """聊天完成选项（流式）"""
    index: int
    delta: ChatMessageDelta
    finish_reason: Optional[str] = None
    logprobs: Optional[Dict[str, Any]] = None


class ChatCompletion(BaseModel):
    """聊天完成响应"""
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: UsageInfo = Field(default_factory=UsageInfo)
    service_tier: Optional[str] = None
    system_fingerprint: Optional[str] = None


class ChatCompletionChunk(BaseModel):
    """聊天完成块（流式响应）"""
    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: List[ChatCompletionStreamChoice]
    usage: Optional[UsageInfo] = None
    system_fingerprint: Optional[str] = None


class EmbeddingData(BaseModel):
    """嵌入数据"""
    object: str = "embedding"
    embedding: List[float]
    index: int


class Embedding(BaseModel):
    """嵌入对象"""
    object: str = "list"
    data: List[EmbeddingData]
    model: str
    usage: UsageInfo = Field(default_factory=UsageInfo)
    encoding_format: str = "float"


class Model(BaseModel):
    """模型信息"""
    id: str
    object: str = "model"
    created: int
    owned_by: str
    permission: Optional[List[Dict[str, Any]]] = None
    root: Optional[str] = None
    parent: Optional[str] = None


class ModelList(BaseModel):
    """模型列表"""
    object: str = "list"
    data: List[Model]


# ============================================================
# 错误模型
# ============================================================


class ErrorResponse(BaseModel):
    """错误响应"""
    error: Dict[str, Any]


# ============================================================
# 工具调用相关
# ============================================================


class ToolCall(BaseModel):
    """工具调用"""
    id: str
    type: str = "function"
    function: Dict[str, str]


class FunctionCallResult(BaseModel):
    """函数调用结果"""
    role: str = "tool"
    content: str
    tool_call_id: str
