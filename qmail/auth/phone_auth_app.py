"""
Standalone FastAPI app for phone authentication only

This is a lightweight server that only handles phone OTP authentication
without importing the heavy crypto dependencies from qmail.api
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
import os
from pathlib import Path

# Import the phone auth router
from qmail.auth.phone_auth_routes import phone_auth_router, initialize_phone_auth
from qmail.auth.otp_service import OtpService
from qmail.auth.token_service import TokenService
from qmail.storage.db import Storage

# ============================================================================
# CREATE FASTAPI APP
# ============================================================================

app = FastAPI(
    title="Qmail Phone Authentication API",
    description="Phone OTP-based authentication for Qmail",
    version="1.0.0",
)

# ============================================================================
# CORS CONFIGURATION
# ============================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# INITIALIZATION
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize services on app startup"""
    database_url = os.environ.get("DATABASE_URL", "sqlite:///./qmail.db")
    if database_url and not database_url.startswith("sqlite"):
        storage = Storage(database_url=database_url, schema="broker")
    else:
        storage = Storage(db_path=Path("qmail.db"))
    
    # Check if Twilio credentials are configured
    twilio_account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    twilio_auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    twilio_phone_number = os.environ.get("TWILIO_PHONE_NUMBER", "")
    use_mock_sms = not (twilio_account_sid and twilio_auth_token and twilio_phone_number)
    
    if use_mock_sms:
        pass
    else:
        pass
    
    otp_service = OtpService(
        storage=storage,
        twilio_account_sid=twilio_account_sid,
        twilio_auth_token=twilio_auth_token,
        twilio_phone_number=twilio_phone_number,
        use_mock_sms=use_mock_sms,
    )
    token_service = TokenService(
        secret_key=os.environ.get("JWT_SECRET_KEY", "your-secret-key-change-in-production"),
        algorithm="HS256",
    )
    
    # Initialize the router with services
    initialize_phone_auth(storage, otp_service, token_service)
    


# ============================================================================
# INCLUDE ROUTER
# ============================================================================

app.include_router(phone_auth_router, prefix="/auth/phone")


# ============================================================================
# HEALTH CHECK ENDPOINT
# ============================================================================

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok", "service": "qmail-phone-auth"}


# ============================================================================
# ROOT ENDPOINT
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Qmail Phone Authentication API",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "qmail.auth.phone_auth_app:app",
        host=os.environ.get("API_HOST", "0.0.0.0"),
        port=int(os.environ.get("API_PORT", "8000")),
        reload=os.environ.get("API_RELOAD", "True").lower() == "true",
    )
