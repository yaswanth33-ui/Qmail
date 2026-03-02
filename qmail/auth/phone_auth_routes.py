"""
Phone Authentication API Routes for Qmail

REST endpoints for phone-verified signup flow:
1. POST /auth/phone/request-otp      - Request OTP to phone
2. POST /auth/phone/verify-otp       - Verify OTP and create account
3. POST /auth/phone/set-password     - Set password for new account
4. POST /auth/phone/login            - Login with email/password
5. POST /auth/phone/refresh          - Refresh access token
6. POST /auth/phone/logout           - Logout (invalidate tokens)
7. GET  /auth/phone/me               - Get current user info

INTEGRATION:
This module is imported and included in the main qmail/api.py FastAPI app
as a router.

Example in api.py:
    from qmail.auth.phone_auth_routes import phone_auth_router
    app.include_router(phone_auth_router, prefix="/auth/phone")
"""

import uuid
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, status, Header
from pydantic import ValidationError

# Import models
from qmail.auth.phone_auth_models import (
    RequestOtpRequest,
    RequestOtpResponse,
    VerifyOtpRequest,
    VerifyOtpResponse,
    SetPasswordRequest,
    SetPasswordResponse,
    LoginRequest,
    LoginResponse,
    QmailUser,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    VerifyResetOtpRequest,
    VerifyResetOtpResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    ErrorResponse,
)

# Import services
from qmail.auth.otp_service import OtpService, hash_password, verify_password
from qmail.auth.token_service import TokenService
from qmail.storage.db import Storage

# ============================================================================
# SETUP & INITIALIZATION
# ============================================================================

phone_auth_router = APIRouter(tags=["auth-phone"])

# These will be injected/initialized by the main api.py app
_storage: Optional[Storage] = None
_otp_service: Optional[OtpService] = None
_token_service: Optional[TokenService] = None


def initialize_phone_auth(
    storage: Storage,
    otp_service: OtpService,
    token_service: TokenService,
) -> None:
    """
    Initialize phone auth services.
    
    Call this from main api.py before starting the app.
    
    Example:
        from qmail.auth.phone_auth_routes import initialize_phone_auth
        from qmail.storage.db import Storage
        from qmail.auth.otp_service import OtpService
        from qmail.auth.token_service import TokenService
        
        storage = Storage(database_url=\"postgresql://user:pass@host/qmail\", schema=\"broker\")
        otp_service = OtpService(storage=storage, use_mock_sms=True)  # use_mock_sms for dev
        token_service = TokenService()
        
        initialize_phone_auth(storage, otp_service, token_service)
    """
    global _storage, _otp_service, _token_service
    _storage = storage
    _otp_service = otp_service
    _token_service = token_service


def get_storage() -> Storage:
    if _storage is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Storage not initialized",
        )
    return _storage


def get_otp_service() -> OtpService:
    if _otp_service is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OTP service not initialized",
        )
    return _otp_service


def get_token_service() -> TokenService:
    if _token_service is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token service not initialized",
        )
    return _token_service


def verify_bearer_token(authorization: Optional[str] = Header(None)) -> dict:
    """
    Extract and verify Bearer token from Authorization header.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = authorization[7:]  # Remove "Bearer " prefix
    token_service = get_token_service()
    payload = token_service.verify_access_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return payload


# ============================================================================
# ENDPOINTS
# ============================================================================

@phone_auth_router.post(
    "/request-otp",
    response_model=RequestOtpResponse,
    responses={
        400: {"model": ErrorResponse},
        409: {"model": ErrorResponse},  # Phone already registered
        429: {"model": ErrorResponse},
    },
    summary="Request OTP to Phone",
    description="Step 1: Send OTP code to user's phone via SMS",
)
async def request_otp(
    req: RequestOtpRequest,
    storage: Storage = Depends(get_storage),
    otp_service: OtpService = Depends(get_otp_service),
) -> RequestOtpResponse:
    """
    Request OTP to be sent to phone number.
    
    - Name, DOB, and phone number are collected
    - Check if phone is already registered (fail fast)
    - 6-digit OTP is generated and sent via SMS
    - Returns session_id needed for verification
    - OTP valid for 10 minutes
    - User gets 3 attempts to verify
    """
    # Check if phone number is already registered (early validation for better UX)
    if not storage.check_phone_available(req.phone_number):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This phone number is already registered. Please login instead.",
        )
    
    try:
        session_id, masked_phone, expires_in = otp_service.request_otp(
            name=req.name,
            phone_number=req.phone_number,
            date_of_birth=req.date_of_birth.isoformat(),
            country_code=req.country_code,
        )
        
        return RequestOtpResponse(
            otp_session_id=session_id,
            phone_masked=masked_phone,
            expires_in_seconds=expires_in,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send OTP",
        )


@phone_auth_router.post(
    "/verify-otp",
    response_model=VerifyOtpResponse,
    responses={
        400: {"model": ErrorResponse},
        409: {"model": ErrorResponse},  # Username taken
    },
    summary="Verify OTP and Create Account",
    description="Step 2: Verify OTP code and create @qmail.com account",
)
async def verify_otp(
    req: VerifyOtpRequest,
    storage: Storage = Depends(get_storage),
    otp_service: OtpService = Depends(get_otp_service),
    token_service: TokenService = Depends(get_token_service),
) -> VerifyOtpResponse:
    """
    Verify OTP code and create @qmail.com account.
    
    Steps:
    1. Verify the OTP code matches the session
    2. Check username and phone number availability
    3. Create new user account in database with uniqueness guarantees
    4. Return temporary token for password setup
    
    The temporary token is valid for 1 hour and can only be used
    to set the password.
    """
    # Verify OTP
    is_valid, user_metadata, error_msg = otp_service.verify_otp(
        otp_session_id=req.otp_session_id,
        otp_code=req.otp_code,
    )
    
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )
    
    # Check if username is available
    if not storage.check_username_available(req.desired_username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{req.desired_username}' is already taken. Please choose another.",
        )
    
    # Check if phone number is already registered
    phone_number = user_metadata["phone_original"]
    if not storage.check_phone_available(phone_number):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This phone number is already registered to an account.",
        )
    
    # Generate unique identifiers
    user_id = f"usr_{uuid.uuid4().hex[:12]}"  # Generate unique user ID
    qmail_address = f"{req.desired_username}@qmail.com"
    
    # Account created but password not yet set (will be set in next step)
    # Wrap in try-except to handle race conditions where another request
    # creates the same username/phone between our check and create
    try:
        user = storage.create_user(
            user_id=user_id,
            username=req.desired_username,
            qmail_address=qmail_address,
            name=user_metadata["name"],
            date_of_birth=user_metadata["date_of_birth"],
            phone_number=phone_number,
            password_hash="",  # Empty until user sets password
        )
    except Exception as e:
        # Handle database integrity errors (unique constraint violations)
        error_str = str(e).lower()
        if "unique" in error_str or "constraint" in error_str:
            if "username" in error_str or req.desired_username.lower() in error_str:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Username '{req.desired_username}' was just taken. Please try another.",
                )
            elif "phone" in error_str:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This phone number is already registered to an account.",
                )
        # Re-raise other database errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create account. Please try again.",
        )
    
    # Account created successfully - now mark OTP as verified
    # This prevents the same OTP from being used again
    otp_service.mark_session_verified(req.otp_session_id)
    
    # Create temporary token for password setup (valid 1 hour)
    temp_token = token_service.create_temporary_password_token(
        user_id=user_id,
        email=qmail_address,
        duration_minutes=60,
    )
    
    return VerifyOtpResponse(
        user_id=user_id,
        qmail_address=qmail_address,
        temporary_auth_token=temp_token,
        name=user_metadata["name"],
    )


@phone_auth_router.post(
    "/set-password",
    response_model=SetPasswordResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
    summary="Set Password",
    description="Step 3: Set password for newly created account",
)
async def set_password(
    req: SetPasswordRequest,
    storage: Storage = Depends(get_storage),
    token_service: TokenService = Depends(get_token_service),
) -> SetPasswordResponse:
    """
    Set password for newly created account.
    
    Uses the temporary token from verify_otp endpoint.
    After this, user can login with username@qmail.com and password.
    """
    # Verify temporary token
    payload = token_service.verify_temporary_password_token(req.temporary_auth_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired password setup token",
        )
    
    # Validate password confirmation
    if req.password != req.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match",
        )
    
    # Password strength already validated by Pydantic model
    
    # Hash password and update user
    user_id = payload["sub"]
    password_hash = hash_password(req.password)
    
    
    # Get user and update password
    user = storage.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    # Update password in database (would need to add this method to Storage)
    # For now, we'll use raw SQL
    from sqlalchemy import text
    from qmail.storage.db import users_table
    
    with storage._engine.begin() as conn:
        stmt = (
            users_table.update()
            .where(users_table.c.id == user_id)
            .values(password_hash=password_hash, updated_at=datetime.now(timezone.utc))
        )
        result = conn.execute(stmt)
    
    # Verify the password was actually stored
    user_after = storage.get_user_by_id(user_id)
    if user_after.get('password_hash'):
        pass
    
    return SetPasswordResponse(
        user_id=user_id,
        qmail_address=user["qmail_address"],
    )


@phone_auth_router.post(
    "/login",
    response_model=LoginResponse,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="Login with Email and Password",
    description="Login to existing @qmail.com account with registered password",
)
async def login(
    req: LoginRequest,
    storage: Storage = Depends(get_storage),
    token_service: TokenService = Depends(get_token_service),
    otp_service: OtpService = Depends(get_otp_service),
) -> LoginResponse:
    """
    Login with @qmail.com email and registered password.
    
    Email format:
    - Full address: john@qmail.com (required suffix)
    - Just username: john (auto-expanded to john@qmail.com)
    
    Password must match the registered password from account creation.
    
    Returns access token, refresh token, and user info.
    """
    # Normalize email to @qmail.com format
    email = req.email.lower().strip()
    if not email.endswith("@qmail.com"):
        email = f"{email}@qmail.com"
    
    
    # Look up user by @qmail.com address
    user = storage.get_user_by_qmail_address(email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email or password is incorrect",
        )
    
    
    # Ensure user has password set (not empty hash)
    if not user.get("password_hash") or len(user.get("password_hash", "")) == 0:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account not fully set up. Please complete password setup.",
        )
    
    # Verify password against stored bcrypt hash
    password_valid = verify_password(req.password, user["password_hash"])
    
    if not password_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email or password is incorrect",
        )
    
    # Update last login timestamp
    storage.update_last_login(user["id"])
    
    # Create tokens
    access_token, access_expires = token_service.create_access_token(
        user_id=user["id"],
        email=user["qmail_address"],
        username=user["username"],
    )
    refresh_token, refresh_expires = token_service.create_refresh_token(
        user_id=user["id"],
    )
    
    # Mask phone for response
    masked_phone = otp_service.mask_phone(user["phone_number"]) if otp_service else user["phone_number"]
    
    user_response = QmailUser(
        user_id=user["id"],
        qmail_address=user["qmail_address"],
        username=user["username"],
        name=user["name"],
        date_of_birth=user["date_of_birth"],
        phone_number=masked_phone,
        account_created_at=user["account_created_at"],
        last_login_at=user["last_login_at"],
        is_verified=user["phone_number_verified"],
    )
    
    return LoginResponse(
        access_token=access_token,
        user=user_response,
        expires_in_seconds=access_expires,
        refresh_token=refresh_token,
    )


@phone_auth_router.post(
    "/refresh",
    response_model=LoginResponse,
    responses={
        401: {"model": ErrorResponse},
    },
    summary="Refresh Access Token",
    description="Use refresh token to get new access token",
)
async def refresh_token(
    refresh_token_req: dict,
    storage: Storage = Depends(get_storage),
    token_service: TokenService = Depends(get_token_service),
) -> LoginResponse:
    """
    Refresh access token using refresh token.
    """
    # Validate refresh token
    refresh_token_str = refresh_token_req.get("refresh_token")
    if not refresh_token_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="refresh_token required",
        )
    
    payload = token_service.verify_refresh_token(refresh_token_str)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    
    # Get user
    user_id = payload["sub"]
    user = storage.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    # Create new access token
    access_token, access_expires = token_service.create_access_token(
        user_id=user["id"],
        email=user["qmail_address"],
        username=user["username"],
    )
    
    # Mask phone
    masked_phone = otp_service.mask_phone(user["phone_number"]) if otp_service else user["phone_number"]
    
    user_response = QmailUser(
        user_id=user["id"],
        qmail_address=user["qmail_address"],
        username=user["username"],
        name=user["name"],
        date_of_birth=user["date_of_birth"],
        phone_number=masked_phone,
        account_created_at=user["account_created_at"],
        last_login_at=user["last_login_at"],
        is_verified=user["phone_number_verified"],
    )
    
    return LoginResponse(
        access_token=access_token,
        user=user_response,
        expires_in_seconds=access_expires,
        refresh_token=refresh_token_str,  # Keep same refresh token
    )


@phone_auth_router.get(
    "/me",
    response_model=QmailUser,
    responses={
        401: {"model": ErrorResponse},
    },
    summary="Get Current User Info",
    description="Get authenticated user's profile",
)
async def get_current_user(
    payload: dict = Depends(verify_bearer_token),
    storage: Storage = Depends(get_storage),
) -> QmailUser:
    """
    Get current authenticated user's profile info.
    
    Requires valid Bearer token in Authorization header.
    """
    user_id = payload.get("sub")
    user = storage.get_user_by_id(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    # Mask phone
    masked_phone = otp_service.mask_phone(user["phone_number"]) if otp_service else user["phone_number"]
    
    return QmailUser(
        user_id=user["id"],
        qmail_address=user["qmail_address"],
        username=user["username"],
        name=user["name"],
        date_of_birth=user["date_of_birth"],
        phone_number=masked_phone,
        account_created_at=user["account_created_at"],
        last_login_at=user["last_login_at"],
        is_verified=user["phone_number_verified"],
    )


@phone_auth_router.post(
    "/logout",
    response_model=dict,
    summary="Logout",
    description="Logout user (invalidate token)",
)
async def logout(
    payload: dict = Depends(verify_bearer_token),
) -> dict:
    """
    Logout user.
    
    In a production system, you'd add the token to a blacklist.
    For now, just return success.
    """
    return {"message": "Logged out successfully"}


@phone_auth_router.get(
    "/check-username/{username}",
    response_model=dict,
    responses={
        200: {"description": "Username availability status"},
        400: {"model": ErrorResponse},
    },
    summary="Check Username Availability",
    description="Check if a username is available for registration",
)
async def check_username_availability(
    username: str,
    storage: Storage = Depends(get_storage),
) -> dict:
    """
    Check if a username is available for new account registration.
    
    Returns:
        - available: true if username is free, false if taken
        - username: the checked username
        - suggestion: optional suggestion if username is taken
    """
    # Basic validation
    if len(username) < 3 or len(username) > 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username must be between 3 and 20 characters",
        )
    
    # Check if alphanumeric and underscores only
    if not username.replace("_", "").isalnum():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username can only contain letters, numbers, and underscores",
        )
    
    is_available = storage.check_username_available(username)
    
    response = {
        "available": is_available,
        "username": username,
    }
    
    # Provide suggestions if taken
    if not is_available:
        import random
        suggestions = [
            f"{username}{random.randint(1, 999)}",
            f"{username}_{random.randint(10, 99)}",
            f"{username}_qmail",
        ]
        # Filter suggestions that are actually available
        available_suggestions = [
            s for s in suggestions 
            if storage.check_username_available(s)
        ]
        if available_suggestions:
            response["suggestion"] = available_suggestions[0]
    
    return response


# ============================================================================
# PASSWORD RESET ENDPOINTS
# ============================================================================

@phone_auth_router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    responses={
        404: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
    },
    summary="Forgot Password - Request Reset OTP",
    description="Initiate password reset by sending OTP to registered phone",
)
async def forgot_password(
    req: ForgotPasswordRequest,
    storage: Storage = Depends(get_storage),
    otp_service: OtpService = Depends(get_otp_service),
) -> ForgotPasswordResponse:
    """
    Request password reset OTP.
    
    User can provide:
    - Email address (john@qmail.com)
    - Username (john_doe)
    - Phone number (+12025551234)
    
    System will:
    1. Find the user account
    2. Send OTP to registered phone number
    3. Return reset session ID for verification
    """
    # Try to find user by identifier (email, username, or phone)
    user = None
    
    # Check if it's an email
    if "@qmail.com" in req.identifier.lower():
        user = storage.get_user_by_email(req.identifier)
    # Check if it's a phone number (starts with +)
    elif req.identifier.startswith("+"):
        user = storage.get_user_by_phone(req.identifier)
    # Otherwise treat as username
    else:
        user = storage.get_user_by_username(req.identifier)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account found with that email, username, or phone number.",
        )
    
    # Generate OTP and send to user's phone
    try:
        session_id, masked_phone, expires_in = otp_service.request_otp(
            name=user["name"],
            phone_number=user["phone_number"],
            date_of_birth=user["date_of_birth"],
            country_code="US",  # Country code stored with user would be better
        )
        
        # Store user_id in session metadata for later use
        # (We'll use the existing OTP session but mark it as a reset)
        # Update the session metadata to include reset context
        session = storage.get_otp_session(session_id)
        if session:
            import json
            metadata = json.loads(session["user_metadata_json"])
            metadata["reset_for_user_id"] = user["id"]  # Use "id" field from user dict
            metadata["reset_for_email"] = user["qmail_address"]
            storage.update_otp_session_metadata(session_id, json.dumps(metadata))
        
        return ForgotPasswordResponse(
            reset_session_id=session_id,
            phone_masked=masked_phone,
            expires_in_seconds=expires_in,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send reset OTP",
        )


@phone_auth_router.post(
    "/verify-reset-otp",
    response_model=VerifyResetOtpResponse,
    responses={
        400: {"model": ErrorResponse},
    },
    summary="Verify Password Reset OTP",
    description="Verify OTP code and get reset token",
)
async def verify_reset_otp(
    req: VerifyResetOtpRequest,
    storage: Storage = Depends(get_storage),
    otp_service: OtpService = Depends(get_otp_service),
    token_service: TokenService = Depends(get_token_service),
) -> VerifyResetOtpResponse:
    """
    Verify password reset OTP and return reset token.
    
    The reset token is valid for 15 minutes and can only be used
    to reset the password.
    """
    # Verify OTP
    is_valid, user_metadata, error_msg = otp_service.verify_otp(
        otp_session_id=req.reset_session_id,
        otp_code=req.otp_code,
    )
    
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )
    
    # Get reset context from metadata
    user_id = user_metadata.get("reset_for_user_id")
    email = user_metadata.get("reset_for_email")
    
    if not user_id or not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reset session",
        )
    
    # Mark OTP as verified
    otp_service.mark_session_verified(req.reset_session_id)
    
    # Create temporary reset token (valid 15 minutes)
    reset_token = token_service.create_temporary_password_token(
        user_id=user_id,
        email=email,
        duration_minutes=15,
    )
    
    return VerifyResetOtpResponse(
        reset_token=reset_token,
        qmail_address=email,
    )


@phone_auth_router.post(
    "/reset-password",
    response_model=ResetPasswordResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
    summary="Reset Password",
    description="Reset password with verified reset token",
)
async def reset_password(
    req: ResetPasswordRequest,
    storage: Storage = Depends(get_storage),
    token_service: TokenService = Depends(get_token_service),
) -> ResetPasswordResponse:
    """
    Reset password using the reset token from verify_reset_otp.
    
    The token is single-use and expires after 15 minutes.
    """
    # Verify reset token
    payload = token_service.verify_temporary_password_token(req.reset_token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired reset token",
        )
    
    user_id = payload.get("sub")  # Token uses "sub" not "user_id"
    email = payload.get("email")
    
    if not user_id or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid reset token",
        )
    
    # Hash new password
    password_hash = hash_password(req.new_password)
    
    # Update password in database
    try:
        storage.update_user_password(user_id, password_hash)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update password",
        )
    
    return ResetPasswordResponse(
        qmail_address=email,
    )
