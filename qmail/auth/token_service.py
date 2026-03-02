"""
JWT Token Service for Qmail Authentication

This module handles:
1. JWT token generation and verification
2. Access tokens (short-lived, 1 hour)
3. Refresh tokens (long-lived, 30 days)
4. Token validation and claims extraction

TOKEN STRUCTURE:
----------------
Access Token (1 hour):
  {
    "sub": "usr_abc123xyz",           # Subject (user_id)
    "email": "john@qmail.com",         # Email address
    "username": "john",                # Username
    "iat": 1645xxx,                    # Issued at
    "exp": 1645xxx + 3600,             # Expires at
    "type": "access",
  }

Refresh Token (30 days):
  {
    "sub": "usr_abc123xyz",            # Subject (user_id)
    "iat": 1645xxx,
    "exp": 1645xxx + 2592000,          # 30 days
    "type": "refresh",
    "jti": "<random>",                 # Token ID for revocation
  }
"""

import os
import json
import secrets
import jwt
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Tuple


class TokenService:
    """Service for JWT token generation and verification."""
    
    # Token configuration (in seconds)
    ACCESS_TOKEN_LIFETIME = 3600  # 1 hour
    REFRESH_TOKEN_LIFETIME = 2592000  # 30 days
    
    def __init__(self, secret_key: Optional[str] = None, algorithm: str = "HS256"):
        """
        Initialize token service.
        
        Args:
            secret_key: Secret key for signing tokens (from env or config)
            algorithm: JWT algorithm (default: HS256)
        """
        if not secret_key:
            secret_key = os.getenv("JWT_SECRET_KEY")
            if not secret_key:
                raise ValueError(
                    "JWT_SECRET_KEY environment variable must be set"
                )
        
        self.secret_key = secret_key
        self.algorithm = algorithm
    
    def create_access_token(
        self,
        user_id: str,
        email: str,
        username: str,
    ) -> Tuple[str, int]:
        """
        Create JWT access token.
        
        Args:
            user_id: User ID from database
            email: User's @qmail.com email
            username: Username
        
        Returns:
            Tuple of (token, expires_in_seconds)
        """
        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=self.ACCESS_TOKEN_LIFETIME)
        
        payload = {
            "sub": user_id,
            "email": email,
            "username": username,
            "iat": int(now.timestamp()),
            "exp": int(expires.timestamp()),
            "type": "access",
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        
        return token, self.ACCESS_TOKEN_LIFETIME
    
    def create_refresh_token(
        self,
        user_id: str,
    ) -> Tuple[str, int]:
        """
        Create JWT refresh token.
        
        Args:
            user_id: User ID from database
        
        Returns:
            Tuple of (token, expires_in_seconds)
        """
        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=self.REFRESH_TOKEN_LIFETIME)
        
        payload = {
            "sub": user_id,
            "iat": int(now.timestamp()),
            "exp": int(expires.timestamp()),
            "type": "refresh",
            "jti": secrets.token_hex(8),  # Unique token ID for revocation tracking
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        
        return token, self.REFRESH_TOKEN_LIFETIME
    
    def create_temporary_password_token(
        self,
        user_id: str,
        email: str,
        duration_minutes: int = 60,
    ) -> str:
        """
        Create temporary token for password setting after OTP verification.
        
        Args:
            user_id: User ID
            email: User's @qmail.com email
            duration_minutes: Token validity in minutes
        
        Returns:
            Temporary token
        """
        now = datetime.now(timezone.utc)
        expires = now + timedelta(minutes=duration_minutes)
        
        payload = {
            "sub": user_id,
            "email": email,
            "iat": int(now.timestamp()),
            "exp": int(expires.timestamp()),
            "type": "temp_password",
        }
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def verify_token(self, token: str) -> Optional[Dict]:
        """
        Verify and decode JWT token.
        
        Args:
            token: JWT token to verify
        
        Returns:
            Decoded payload dict on success, None on failure
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
            )
            return payload
        except jwt.ExpiredSignatureError:
            return None  # Token expired
        except jwt.InvalidTokenError:
            return None  # Invalid token
    
    def verify_access_token(self, token: str) -> Optional[Dict]:
        """
        Verify access token specifically.
        
        Returns:
            Decoded payload if valid access token, None otherwise
        """
        payload = self.verify_token(token)
        if not payload or payload.get("type") != "access":
            return None
        return payload
    
    def verify_refresh_token(self, token: str) -> Optional[Dict]:
        """
        Verify refresh token specifically.
        
        Returns:
            Decoded payload if valid refresh token, None otherwise
        """
        payload = self.verify_token(token)
        if not payload or payload.get("type") != "refresh":
            return None
        return payload
    
    def verify_temporary_password_token(self, token: str) -> Optional[Dict]:
        """
        Verify temporary password token.
        
        Returns:
            Decoded payload if valid, None otherwise
        """
        payload = self.verify_token(token)
        if not payload or payload.get("type") != "temp_password":
            return None
        return payload
    
    def extract_user_id(self, token: str) -> Optional[str]:
        """Extract user_id from token without verification (use with caution)."""
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
            )
            return payload.get("sub")
        except:
            return None
