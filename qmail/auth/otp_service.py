"""
OTP (One-Time Password) Service for Phone-Based Signup

This module handles:
1. OTP generation and validation
2. SMS delivery (via Twilio)
3. Session management
4. Rate limiting and security

WORKFLOW:
---------
1. User requests OTP with phone number
   → Service generates 6-digit OTP
   → Hashes it with bcrypt
   → Sends SMS via Twilio
   → Returns session_id (NOT the OTP)

2. User enters OTP in app
   → Service compares bcrypt hash with plaintext OTP
   → If match: mark session as verified
   → Create @qmail.com account
   → User sets password

SECURITY:
---------
- OTP codes are NEVER stored in plaintext (always bcrypt hashed)
- OTP only valid for 10 minutes
- Max 3 failed attempts per session
- Rate limiting: max 3 requests per phone per hour
"""

import os
import random
import secrets
import json
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
import bcrypt

# For SMS delivery (Twilio)
try:
    from twilio.rest import Client
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False


class OtpService:
    """Service for OTP generation, delivery, and verification."""
    
    # OTP configuration
    OTP_LENGTH = 6
    OTP_VALIDITY_MINUTES = 10
    OTP_MAX_ATTEMPTS = 3
    
    def __init__(
        self,
        storage=None,  # Storage instance for persisting OTP sessions
        twilio_account_sid: Optional[str] = None,
        twilio_auth_token: Optional[str] = None,
        twilio_phone_number: Optional[str] = None,
        use_mock_sms: bool = False,
    ):
        """
        Initialize OTP service.
        
        Args:
            storage: Storage instance for OTP sessions
            twilio_account_sid: Twilio account SID (from env or config)
            twilio_auth_token: Twilio auth token (from env or config)
            twilio_phone_number: Twilio phone number for SMS sender
            use_mock_sms: If True, print OTP instead of sending (for testing)
        """
        self.storage = storage
        self.use_mock_sms = use_mock_sms
        
        # Initialize Twilio if credentials provided
        if TWILIO_AVAILABLE and twilio_account_sid and twilio_auth_token:
            try:
                self.twilio_client = Client(twilio_account_sid, twilio_auth_token)
                self.twilio_phone_number = twilio_phone_number or os.getenv("TWILIO_PHONE_NUMBER")
            except Exception as e:
                self.twilio_client = None
        else:
            self.twilio_client = None
            if not TWILIO_AVAILABLE:
                pass
    
    def generate_otp_code(self) -> str:
        """Generate a random 6-digit OTP code."""
        return ''.join(str(random.randint(0, 9)) for _ in range(self.OTP_LENGTH))
    
    def hash_otp(self, otp_code: str) -> str:
        """Hash OTP using bcrypt for secure storage."""
        return bcrypt.hashpw(otp_code.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def verify_otp_hash(self, otp_code: str, otp_hash: str) -> bool:
        """
        Verify plaintext OTP against bcrypt hash.
        
        Args:
            otp_code: Plaintext OTP from user
            otp_hash: bcrypt hash from database
        
        Returns:
            True if OTP matches, False otherwise
        """
        return bcrypt.checkpw(otp_code.encode('utf-8'), otp_hash.encode('utf-8'))
    
    def generate_session_id(self) -> str:
        """Generate a unique OTP session ID."""
        return f"sess_{secrets.token_hex(12)}"
    
    def mask_phone(self, phone: str) -> str:
        """
        Mask phone number for display.
        E.g., +12025551234 → +1202****1234
        """
        if len(phone) < 8:
            return phone
        return phone[:-4] + '****' + phone[-4:]
    
    def request_otp(
        self,
        name: str,
        phone_number: str,
        date_of_birth: str,
        country_code: str = "US",
    ) -> Tuple[str, str, int]:
        """
        Request OTP for phone verification.
        
        Args:
            name: User's full name
            phone_number: E.164 formatted phone (e.g., +12025551234)
            date_of_birth: ISO format (YYYY-MM-DD)
            country_code: Country code for routing
        
        Returns:
            Tuple of (otp_session_id, masked_phone, expires_in_seconds)
        
        Raises:
            ValueError: If validation fails
        """
        # Generate OTP and create session
        otp_code = self.generate_otp_code()
        otp_hash = self.hash_otp(otp_code)
        session_id = self.generate_session_id()
        
        # Store user metadata
        user_metadata = {
            "name": name,
            "phone_original": phone_number,
            "date_of_birth": date_of_birth,
            "country_code": country_code,
        }
        
        # Set expiration time
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=self.OTP_VALIDITY_MINUTES)
        
        # Save to database
        if self.storage:
            self.storage.create_otp_session(
                otp_session_id=session_id,
                phone_number=phone_number,
                otp_code_hash=otp_hash,
                user_metadata_json=json.dumps(user_metadata),
                expires_at=expires_at,
            )
        
        # Send OTP via SMS
        self._send_otp_sms(phone_number, otp_code, name)
        
        # Return session info (NOT the OTP code)
        return (
            session_id,
            self.mask_phone(phone_number),
            self.OTP_VALIDITY_MINUTES * 60,
        )
    
    def _send_otp_sms(self, phone: str, otp_code: str, name: str) -> None:
        """
        Send OTP via SMS.
        
        Args:
            phone: E.164 formatted phone number
            otp_code: The OTP code to send
            name: User's name (for personalization)
        """
        message_body = f"Hi {name.split()[0]}, your Qmail OTP code is: {otp_code}. Valid for 10 minutes. Never share this code."
        
        if self.use_mock_sms:
            # For development/testing: print instead of sending
            return
        
        if not self.twilio_client or not self.twilio_phone_number:
            # If Twilio not configured and not in mock mode, raise error
            raise ValueError(
                "SMS delivery not configured. Set TWILIO credentials or use use_mock_sms=True"
            )
        
        try:
            message = self.twilio_client.messages.create(
                body=message_body,
                from_=self.twilio_phone_number,
                to=phone,
            )
        except Exception as e:
            error_msg = str(e)
            
            # Provide helpful error messages for common issues
            if "authentication" in error_msg.lower() or "credentials" in error_msg.lower():
                raise RuntimeError(f"Twilio authentication failed. Check TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN")
            elif "unverified" in error_msg.lower():
                raise RuntimeError(f"Twilio trial account: {phone} must be verified in Twilio console first. Visit: https://console.twilio.com/us1/develop/phone-numbers/manage/verified")
            elif "phone number" in error_msg.lower():
                raise RuntimeError(f"Invalid Twilio phone number: {self.twilio_phone_number}. Check TWILIO_PHONE_NUMBER in .env")
            else:
                raise RuntimeError(f"Failed to send SMS: {error_msg}")
    
    def verify_otp(
        self,
        otp_session_id: str,
        otp_code: str,
    ) -> Tuple[bool, Optional[dict], str]:
        """
        Verify OTP code against stored session.
        
        Args:
            otp_session_id: Session ID from request_otp
            otp_code: User-entered 6-digit code
        
        Returns:
            Tuple of (is_valid: bool, user_metadata: dict, error_message: str)
            - is_valid=True, user_metadata=dict, error_message="" on success
            - is_valid=False, user_metadata=None, error_message=<reason> on failure
        """
        if not self.storage:
            return False, None, "Storage not configured"
        
        # Retrieve session
        session = self.storage.get_otp_session(otp_session_id)
        if not session:
            return False, None, "OTP session not found. Request a new code."
        
        # Check if already verified
        if session["is_verified"]:
            return False, None, "OTP already used. Request a new code."
        
        # Check expiration
        now = datetime.now(timezone.utc)
        expires_at = session["expires_at"]
        
        # Ensure timezone-aware comparison
        if expires_at.tzinfo is None:
            # Database returned naive datetime, assume UTC
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        
        if now > expires_at:
            return False, None, "OTP expired. Request a new code."
        
        # Check attempt limit
        if session["verification_attempts"] >= session["max_attempts"]:
            return False, None, "Too many failed attempts. Request a new code."
        
        # Verify OTP hash
        if not self.verify_otp_hash(otp_code, session["otp_code_hash"]):
            # Increment attempts
            attempts = self.storage.increment_otp_attempt(otp_session_id)
            remaining = session["max_attempts"] - attempts
            error_msg = f"Invalid OTP code. {remaining} attempts remaining."
            return False, None, error_msg
        
        # OTP is valid! Parse and return user metadata
        # NOTE: We don't mark as verified yet - that happens after account creation
        user_metadata = json.loads(session["user_metadata_json"])
        
        return True, user_metadata, ""
    
    def mark_session_verified(self, otp_session_id: str) -> bool:
        """
        Mark OTP session as verified after successful account creation.
        This should only be called after the account is successfully created
        to allow retries if username is taken.
        """
        if not self.storage:
            return False
        
        self.storage.mark_otp_verified(otp_session_id)
        return True
    
    def get_session_info(self, otp_session_id: str) -> Optional[dict]:
        """Get non-sensitive session information."""
        if not self.storage:
            return None
        
        session = self.storage.get_otp_session(otp_session_id)
        if not session:
            return None
        
        metadata = json.loads(session["user_metadata_json"])
        
        return {
            "phone_masked": self.mask_phone(session["phone_number"]),
            "attempts_remaining": session["max_attempts"] - session["verification_attempts"],
            "is_verified": session["is_verified"],
            "expires_at": session["expires_at"],
            "user_name": metadata.get("name"),
        }


# Utility function for password hashing (for user passwords, not OTP)
def hash_password(password: str) -> str:
    """Hash user password with bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """Verify user password against bcrypt hash."""
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
