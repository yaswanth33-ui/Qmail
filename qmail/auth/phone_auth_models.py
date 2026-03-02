"""
Phone Number Authentication Models for Qmail

This module defines request/response models for phone-based signup with OTP verification.

SIGNUP FLOW:
1. User provides name, DOB, phone number
2. Server generates OTP and sends to phone (SMS/Twilio)
3. User verifies OTP in app
4. Server creates @qmail.com account
5. User sets password
6. Account ready for login

ENDPOINTS:
- POST /auth/phone/request-otp     - Send OTP to phone
- POST /auth/phone/verify-otp      - Verify OTP + create account
- POST /auth/phone/set-password    - Set password after account creation
- POST /auth/phone/login           - Login with email/password
"""

from pydantic import BaseModel, Field, EmailStr, field_validator
from typing import Optional
from datetime import date, datetime, timedelta


class RequestOtpRequest(BaseModel):
    """
    Step 1: Request OTP to be sent to phone number.
    User provides name, DOB, and phone to start signup.
    Must be 18+ years old.
    """
    name: str = Field(..., min_length=2, max_length=100, description="Full name")
    date_of_birth: date = Field(..., description="Date of birth (YYYY-MM-DD). Must be 18+ years old.")
    phone_number: str = Field(
        ..., 
        pattern=r'^\+?1?\d{9,15}$',  # E.164 format, optional +1 for countries
        description="Phone number in E.164 format (e.g., +1234567890)"
    )
    country_code: str = Field(default="US", description="Country code for SMS routing")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "John Doe",
                    "date_of_birth": "1990-05-15",
                    "phone_number": "+12025551234",
                    "country_code": "US"
                }
            ]
        }
    }
    
    @field_validator('date_of_birth')
    @classmethod
    def validate_age_18_or_older(cls, v):
        """Ensure user is 18 years or older."""
        today = date.today()
        age = today.year - v.year - ((today.month, today.day) < (v.month, v.day))
        
        if age < 18:
            raise ValueError('You must be at least 18 years old to create an account')
        
        # Also check it's not a future date
        if v > today:
            raise ValueError('Date of birth cannot be in the future')
        
        return v


class RequestOtpResponse(BaseModel):
    """Response after OTP is sent successfully."""
    otp_session_id: str = Field(..., description="Session ID to track OTP verification")
    phone_masked: str = Field(..., description="Masked phone (e.g., +1202****1234)")
    expires_in_seconds: int = Field(default=600, description="OTP valid for 10 minutes")
    message: str = "OTP sent successfully. Check your phone for the 6-digit code."
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "otp_session_id": "sess_abc123xyz",
                    "phone_masked": "+1202****1234",
                    "expires_in_seconds": 600,
                    "message": "OTP sent successfully. Check your phone for the 6-digit code."
                }
            ]
        }
    }


class VerifyOtpRequest(BaseModel):
    """
    Step 2: Verify OTP and create @qmail.com account.
    User enters the 6-digit OTP they received.
    """
    otp_session_id: str = Field(..., description="Session ID from RequestOtp response")
    otp_code: str = Field(
        ..., 
        pattern=r'^\d{6}$',
        description="6-digit OTP code"
    )
    desired_username: str = Field(
        ..., 
        pattern=r'^[a-zA-Z0-9_-]{3,20}$',
        description="Username for @qmail.com address (3-20 chars, alphanumeric + underscore/hyphen)"
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "otp_session_id": "sess_abc123xyz",
                    "otp_code": "123456",
                    "desired_username": "john_doe"
                }
            ]
        }
    }
    
    @field_validator('desired_username')
    @classmethod
    def validate_username(cls, v):
        """Ensure username isn't reserved."""
        reserved = {'admin', 'root', 'system', 'qmail', 'noreply', 'support', 'dev'}
        if v.lower() in reserved:
            raise ValueError(f'Username "{v}" is reserved')
        return v


class VerifyOtpResponse(BaseModel):
    """
    Response after successful OTP verification.
    Account is created, now user needs to set password.
    """
    user_id: str = Field(..., description="Unique user ID")
    qmail_address: str = Field(..., description="New @qmail.com email address")
    temporary_auth_token: str = Field(
        ..., 
        description="Temporary token for setting password (valid for 1 hour)"
    )
    name: str = Field(..., description="User's full name")
    message: str = "Account created! Now set your password to complete signup."
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "user_id": "usr_abc123xyz",
                    "qmail_address": "john_doe@qmail.com",
                    "temporary_auth_token": "temp_token_abc123xyz",
                    "name": "John Doe",
                    "message": "Account created! Now set your password to complete signup."
                }
            ]
        }
    }


class SetPasswordRequest(BaseModel):
    """
    Step 3: Set password for the newly created account.
    User provides the password they want to use.
    """
    temporary_auth_token: str = Field(..., description="Temporary token from VerifyOtp")
    password: str = Field(
        ..., 
        min_length=8,
        description="Password (min 8 chars, must include uppercase, lowercase, number, special char)"
    )
    confirm_password: str = Field(..., description="Confirm password")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "temporary_auth_token": "temp_token_abc123xyz",
                    "password": "SecurePass123!",
                    "confirm_password": "SecurePass123!"
                }
            ]
        }
    }
    
    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v):
        """Validate password meets security requirements."""
        has_upper = any(c.isupper() for c in v)
        has_lower = any(c.islower() for c in v)
        has_digit = any(c.isdigit() for c in v)
        has_special = any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in v)
        
        if not (has_upper and has_lower and has_digit and has_special):
            raise ValueError(
                'Password must include uppercase, lowercase, number, and special character'
            )
        return v


class SetPasswordResponse(BaseModel):
    """Response after password is set successfully."""
    user_id: str = Field(..., description="User ID")
    qmail_address: str = Field(..., description="@qmail.com address")
    message: str = "Password set successfully! You can now login."
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "user_id": "usr_abc123xyz",
                    "qmail_address": "john_doe@qmail.com",
                    "message": "Password set successfully! You can now login."
                }
            ]
        }
    }


class LoginRequest(BaseModel):
    """Login with @qmail.com email and registered password."""
    email: str = Field(
        ..., 
        description="Email address (@qmail.com required). Can be username@qmail.com or just username"
    )
    password: str = Field(..., min_length=1, description="Password (must match registered password)")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "email": "john_doe@qmail.com",
                    "password": "SecurePass123!"
                }
            ]
        }
    }
    
    @field_validator('email')
    @classmethod
    def validate_email_format(cls, v):
        """Ensure email is in valid @qmail.com format or just username."""
        v = v.lower().strip()
        
        # If it contains @, it must be @qmail.com
        if '@' in v:
            if not v.endswith('@qmail.com'):
                raise ValueError('Email must be @qmail.com address (e.g., username@qmail.com)')
        
        # Validate email/username format (alphanumeric, underscore, hyphen)
        email_part = v.split('@')[0] if '@' in v else v
        if not all(c.isalnum() or c in '_-' for c in email_part):
            raise ValueError('Email format invalid. Use alphanumeric characters, underscore, or hyphen')
        
        # Ensure not empty
        if not email_part or len(email_part) < 3:
            raise ValueError('Email/username must be at least 3 characters')
        
        return v


class QmailUser(BaseModel):
    """User profile model returned after login/verification."""
    user_id: str = Field(..., description="Unique user ID")
    qmail_address: str = Field(..., description="@qmail.com email address")
    username: str = Field(..., description="Username (before @qmail.com)")
    name: str = Field(..., description="Full name")
    date_of_birth: date = Field(..., description="Date of birth")
    phone_number: str = Field(..., description="Phone number (masked)")
    account_created_at: datetime = Field(..., description="Account registration time")
    last_login_at: Optional[datetime] = Field(None, description="Last login time")
    is_verified: bool = Field(default=True, description="Phone verified")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "user_id": "usr_abc123xyz",
                    "qmail_address": "john_doe@qmail.com",
                    "username": "john_doe",
                    "name": "John Doe",
                    "date_of_birth": "1990-05-15",
                    "phone_number": "+1202****1234",
                    "account_created_at": "2026-02-17T10:30:00Z",
                    "last_login_at": "2026-02-17T15:45:00Z",
                    "is_verified": True
                }
            ]
        }
    }


class LoginResponse(BaseModel):
    """Response after successful login."""
    access_token: str = Field(..., description="JWT token for API calls")
    token_type: str = Field(default="Bearer", description="Token type")
    user: QmailUser = Field(..., description="User profile")
    expires_in_seconds: int = Field(default=3600, description="Token valid for 1 hour")
    refresh_token: Optional[str] = Field(None, description="Token to refresh access_token")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "token_type": "Bearer",
                    "user": {
                        "user_id": "usr_abc123xyz",
                        "qmail_address": "john_doe@qmail.com",
                        "username": "john_doe",
                        "name": "John Doe",
                        "date_of_birth": "1990-05-15",
                        "phone_number": "+1202****1234",
                        "account_created_at": "2026-02-17T10:30:00Z",
                        "last_login_at": "2026-02-17T15:45:00Z",
                        "is_verified": True
                    },
                    "expires_in_seconds": 3600,
                    "refresh_token": "refresh_token_xyz123abc"
                }
            ]
        }
    }


class ForgotPasswordRequest(BaseModel):
    """Request to initiate password reset."""
    identifier: str = Field(
        ..., 
        description="Email address, username, or phone number (+E.164 format)"
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "identifier": "john_doe@qmail.com"
                },
                {
                    "identifier": "john_doe"
                },
                {
                    "identifier": "+12025551234"
                }
            ]
        }
    }


class ForgotPasswordResponse(BaseModel):
    """Response after requesting password reset."""
    reset_session_id: str = Field(..., description="Session ID for reset verification")
    phone_masked: str = Field(..., description="Masked phone number where OTP was sent")
    expires_in_seconds: int = Field(default=600, description="OTP valid for 10 minutes")
    message: str = "Password reset OTP sent to your phone."


class VerifyResetOtpRequest(BaseModel):
    """Request to verify password reset OTP."""
    reset_session_id: str = Field(..., description="Session ID from forgot password request")
    otp_code: str = Field(
        ..., 
        pattern=r'^\d{6}$',
        description="6-digit OTP code"
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "reset_session_id": "sess_abc123xyz",
                    "otp_code": "123456"
                }
            ]
        }
    }


class VerifyResetOtpResponse(BaseModel):
    """Response after verifying reset OTP."""
    reset_token: str = Field(..., description="Temporary token to reset password (valid 15 minutes)")
    qmail_address: str = Field(..., description="Email address for the account")
    message: str = "OTP verified. You can now reset your password."


class ResetPasswordRequest(BaseModel):
    """Request to reset password with verified token."""
    reset_token: str = Field(..., description="Token from verify reset OTP")
    new_password: str = Field(
        ..., 
        min_length=8,
        description="New password (min 8 characters)"
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "reset_token": "reset_token_xyz123",
                    "new_password": "NewSecurePassword123!"
                }
            ]
        }
    }


class ResetPasswordResponse(BaseModel):
    """Response after successful password reset."""
    message: str = "Password reset successful. You can now login with your new password."
    qmail_address: str = Field(..., description="Email address for the account")


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    details: Optional[dict] = Field(None, description="Additional error details")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "error": "INVALID_OTP",
                    "message": "The OTP code you entered is incorrect",
                    "details": {"attempts_remaining": 2}
                }
            ]
        }
    }
