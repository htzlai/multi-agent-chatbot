"""
Supabase JWT Authentication for FastAPI Backend
Verifies JWT tokens from Supabase Cloud Auth
"""

import os
import httpx
from fastapi import Depends, HTTPException, status, Query, WebSocket
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from functools import lru_cache

try:
    from jose import jwt, jwk
    from jose.exceptions import JWTError, ExpiredSignatureError
    JOSE_AVAILABLE = True
except ImportError:
    JOSE_AVAILABLE = False

security = HTTPBearer(auto_error=False)

SUPABASE_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL", "")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")


@lru_cache()
def get_jwks() -> dict:
    """Fetch JWKS from Supabase for token verification"""
    if not SUPABASE_URL:
        raise ValueError("NEXT_PUBLIC_SUPABASE_URL not configured")
    
    jwks_url = f"{SUPABASE_URL}/.well-known/jwks.json"
    
    with httpx.Client() as client:
        response = client.get(jwks_url, timeout=10.0)
        response.raise_for_status()
        return response.json()


def verify_token(token: str) -> dict:
    """Verify a Supabase JWT token and return the payload"""
    if not JOSE_AVAILABLE:
        raise ImportError("python-jose[cryptography] is required for JWT verification")
    
    if not SUPABASE_JWT_SECRET:
        raise ValueError("SUPABASE_JWT_SECRET not configured")
    
    try:
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            options={
                "verify_aud": False,
                "verify_iss": False,
            }
        )
        return payload
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> dict:
    """FastAPI dependency to get the current authenticated user from JWT"""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    token = credentials.credentials
    payload = verify_token(token)
    
    return {
        "id": payload.get("sub"),
        "email": payload.get("email"),
        "role": payload.get("role", "authenticated"),
        "aud": payload.get("aud"),
    }


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[dict]:
    """FastAPI dependency to optionally get the current user (no error if not authenticated)"""
    if credentials is None:
        return None
    
    try:
        token = credentials.credentials
        payload = verify_token(token)
        return {
            "id": payload.get("sub"),
            "email": payload.get("email"),
            "role": payload.get("role", "authenticated"),
        }
    except HTTPException:
        return None


async def verify_websocket_token(token: str) -> dict:
    """Verify token for WebSocket connections"""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token required for WebSocket connection"
        )
    
    return verify_token(token)
