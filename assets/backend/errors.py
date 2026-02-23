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
"""
统一错误处理模块

提供标准化的错误响应格式，遵循 RFC 7807 Problem Details for HTTP APIs 规范
"""

from typing import Optional, Dict, Any
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorCode:
    """预定义错误码"""
    # 通用错误
    UNKNOWN_ERROR = "UNKNOWN_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    
    # 认证错误
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    TOKEN_INVALID = "TOKEN_INVALID"
    
    # 资源错误
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    RESOURCE_ALREADY_EXISTS = "RESOURCE_ALREADY_EXISTS"
    RESOURCE_CONFLICT = "RESOURCE_CONFLICT"
    
    # 速率限制
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    
    # RAG/知识库错误
    RAG_QUERY_ERROR = "RAG_QUERY_ERROR"
    SOURCE_NOT_FOUND = "SOURCE_NOT_FOUND"
    INDEXING_FAILED = "INDEXING_FAILED"
    
    # 会话错误
    CHAT_NOT_FOUND = "CHAT_NOT_FOUND"
    MESSAGE_NOT_FOUND = "MESSAGE_NOT_FOUND"


class APIErrorResponse(BaseModel):
    """统一错误响应格式"""
    error: Dict[str, Any]


class APIError(Exception):
    """自定义 API 错误类
    
    使用方式:
        raise APIError(ErrorCode.NOT_FOUND, "资源不存在", status_code=404)
    """
    
    def __init__(
        self, 
        code: str, 
        message: str, 
        status_code: int = 400,
        details: Optional[Dict[str, Any]] = None
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details
            }
        }
    
    def to_http_exception(self) -> HTTPException:
        """转换为 FastAPI HTTPException"""
        return HTTPException(
            status_code=self.status_code,
            detail=self.to_dict()
        )


class NotFoundError(APIError):
    """资源不存在错误"""
    def __init__(self, resource: str, resource_id: str = None):
        message = f"{resource} not found"
        if resource_id:
            message = f"{resource} '{resource_id}' not found"
        super().__init__(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message=message,
            status_code=404,
            details={"resource": resource, "resource_id": resource_id}
        )


class UnauthorizedError(APIError):
    """未认证错误"""
    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            code=ErrorCode.UNAUTHORIZED,
            message=message,
            status_code=401
        )


class ForbiddenError(APIError):
    """禁止访问错误"""
    def __init__(self, message: str = "Access denied"):
        super().__init__(
            code=ErrorCode.FORBIDDEN,
            message=message,
            status_code=403
        )


class ValidationError(APIError):
    """验证错误"""
    def __init__(self, message: str, field: str = None):
        details = {"field": field} if field else {}
        super().__init__(
            code=ErrorCode.VALIDATION_ERROR,
            message=message,
            status_code=400,
            details=details
        )


class InternalError(APIError):
    """内部服务器错误"""
    def __init__(self, message: str = "Internal server error", details: Dict = None):
        super().__init__(
            code=ErrorCode.INTERNAL_ERROR,
            message=message,
            status_code=500,
            details=details
        )


class RateLimitError(APIError):
    """速率限制错误"""
    def __init__(self, retry_after: int = 60):
        super().__init__(
            code=ErrorCode.RATE_LIMIT_EXCEEDED,
            message="Rate limit exceeded, please try again later",
            status_code=429,
            details={"retry_after": retry_after}
        )


def create_error_response(
    code: str, 
    message: str, 
    status_code: int = 400,
    details: Dict = None
) -> JSONResponse:
    """创建统一格式的错误响应
    
    Args:
        code: 错误码
        message: 错误消息
        status_code: HTTP 状态码
        details: 额外详情
    
    Returns:
        JSONResponse
    """
    content = {
        "error": {
            "code": code,
            "message": message,
        }
    }
    
    if details:
        content["error"]["details"] = details
    
    return JSONResponse(
        status_code=status_code,
        content=content
    )


def not_found_error(resource: str, resource_id: str = None) -> JSONResponse:
    """快速创建 404 错误响应"""
    message = f"{resource} not found"
    if resource_id:
        message = f"{resource} '{resource_id}' not found"
    return create_error_response(
        code=ErrorCode.RESOURCE_NOT_FOUND,
        message=message,
        status_code=404,
        details={"resource": resource, "resource_id": resource_id}
    )


def validation_error(message: str, field: str = None) -> JSONResponse:
    """快速创建 400 验证错误响应"""
    details = {"field": field} if field else {}
    return create_error_response(
        code=ErrorCode.VALIDATION_ERROR,
        message=message,
        status_code=400,
        details=details
    )


def unauthorized_error(message: str = "Authentication required") -> JSONResponse:
    """快速创建 401 未认证错误响应"""
    return create_error_response(
        code=ErrorCode.UNAUTHORIZED,
        message=message,
        status_code=401
    )


def forbidden_error(message: str = "Access denied") -> JSONResponse:
    """快速创建 403 禁止访问错误响应"""
    return create_error_response(
        code=ErrorCode.FORBIDDEN,
        message=message,
        status_code=403
    )


def internal_error(message: str = "Internal server error", details: Dict = None) -> JSONResponse:
    """快速创建 500 内部错误响应"""
    return create_error_response(
        code=ErrorCode.INTERNAL_ERROR,
        message=message,
        status_code=500,
        details=details
    )
