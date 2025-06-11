from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from typing import Dict, Any, Optional
import logging
from datetime import datetime, timedelta
import uuid
import jwt
from jwt import PyJWTError, DecodeError, ExpiredSignatureError  # Update imports
import asyncio
from fastapi.responses import JSONResponse
from fastapi import BackgroundTasks
from collections import defaultdict
import time
from bson import ObjectId  # Add this import at the top

from config import settings
from services.auth_service import (
    authenticate_user,
    generate_auth_tokens,
    create_user,
    authenticate_social_user,
    create_password_reset_token,
    reset_password,
    verify_email,
    get_user_by_email,
    get_user_by_id,
    get_user_by_reset_token,
    get_password_hash  # Now this will work
)
from services.email_service import (
    send_verification_email,
    send_password_reset_email,
    send_verification_success_email,
    send_password_reset_notification
)
from models.user import UserCreate
from models.auth import (
    SocialLoginInput,
    TokenResponse,
    PasswordResetRequest,
    PasswordReset,
    EmailVerificationRequest,
    EmailVerificationResponse,
    PasswordResetResponse,
)
from models.database import users, blacklisted_tokens
from models.database import verification_tokens
from services.social_auth import handle_social_login
from services.google_auth import handle_google_auth  # Add this import

# Simple in-memory rate limiting
rate_limits = defaultdict(list)
RATE_LIMIT_DURATION = 60  # 1 minute
RATE_LIMIT_ATTEMPTS = 5

def check_rate_limit(client_ip: str) -> bool:
    """Check if client has exceeded rate limit"""
    now = time.time()
    # Clean old entries
    rate_limits[client_ip] = [t for t in rate_limits[client_ip] if now - t < RATE_LIMIT_DURATION]
    # Check limit
    if len(rate_limits[client_ip]) >= RATE_LIMIT_ATTEMPTS:
        return False
    rate_limits[client_ip].append(now)
    return True

# Update router definition - remove prefix as it's defined in main.py
router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

logger = logging.getLogger(__name__)

async def get_current_user(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET_KEY, 
            algorithms=[settings.JWT_ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except PyJWTError:
        raise credentials_exception
        
    user = await get_user_by_id(user_id)
    if user is None:
        raise credentials_exception
    return user

@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(user_data: UserCreate) -> Dict[str, Any]:
    try:
        logger.info(f"Signup attempt for email: {user_data.email}")
        
        # Check for existing user
        existing_user = await users.find_one({"email": user_data.email})
        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="User with this email already exists"
            )
        
        # Generate verification token
        verification_token = str(uuid.uuid4())
        
        # Create user document with hashed password
        user = {
            "name": user_data.name,
            "email": user_data.email,
            "username": user_data.email,  # Using email as default username
            "password_hash": get_password_hash(user_data.password),  # Now this will work
            "phone": user_data.phone,
            "is_verified": False,
            "verification_token": verification_token,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # Send verification email first
        email_sent = await send_verification_email(
            user_data.email,
            user_data.name,
            verification_token
        )
        
        if not email_sent:
            logger.error(f"Failed to send verification email to: {user_data.email}")
            raise HTTPException(
                status_code=500,
                detail="Failed to send verification email"
            )
            
        # Insert user if email was sent successfully
        result = await users.insert_one(user)
        if not result.inserted_id:
            raise HTTPException(
                status_code=500,
                detail="Failed to create user"
            )

        return {
            "success": True,
            "message": "User created successfully. Please check your email for verification.",
            "email": user_data.email
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Signup error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error during signup"
        )

@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
    """OAuth2 compatible token login"""
    try:
        success, user, error = await authenticate_user(
            form_data.username,
            form_data.password
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=error,
                headers={"WWW-Authenticate": "Bearer"},
            )

        tokens = await generate_auth_tokens(user)
        user_data = {
            "id": str(user["_id"]),
            "email": user["email"],
            "name": user["name"],
            "is_verified": user.get("is_verified", False),
            "profile_image": user.get("profile_image"),
            "name_avatar": user.get("name_avatar")
        }
        
        return {
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "token_type": "bearer",
            "user": user_data
        }
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

@router.post("/social-login", response_model=TokenResponse)
async def social_login(data: SocialLoginInput):
    success, user, error = await authenticate_social_user(
        provider=data.provider,
        provider_user_id=data.provider_user_id,
        email=data.email,
        name=data.name
    )
    if not success:
        raise HTTPException(status_code=400, detail=error)
    return await generate_auth_tokens(user)

@router.post("/forgot-password")
async def forgot_password(data: PasswordResetRequest):
    success, token, message = await create_password_reset_token(data.email)
    if success and token:
        # Send password reset email
        user = await get_user_by_email(data.email)
        email_sent = await send_password_reset_email(
            data.email,
            user["name"],
            token
        )
        if not email_sent:
            logger.error(f"Failed to send password reset email to {data.email}")
            raise HTTPException(
                status_code=500,
                detail="Failed to send password reset email. Please try again."
            )
        logger.info(f"Password reset email sent to {data.email}")
    
    # Don't reveal if email exists
    return {"message": "If your email is registered, you will receive a password reset link."}

@router.post("/reset-password", response_model=PasswordResetResponse)
async def password_reset(data: PasswordReset):
    """Reset password using reset token"""
    try:
        logger.info("Attempting password reset")
        success, error, user = await reset_password(data.token, data.new_password)
        
        if not success:
            logger.error(f"Password reset failed: {error}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error
            )
        
        # Send confirmation email
        if user:
            logger.info(f"Sending password reset confirmation email to {user['email']}")
            email_sent = await send_password_reset_notification(user["email"], user["name"])
            if not email_sent:
                logger.error(f"Failed to send password reset confirmation to {user['email']}")
                # Don't fail the request if email fails
            
        logger.info("Password reset successful")
        return PasswordResetResponse(
            message="Your password has been reset successfully",
            success=True
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error in password_reset: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while resetting password"
        )

@router.get("/verify-email/{token}/status")
async def check_verification_status(token: str):
    """Check if email is already verified"""
    try:
        # Check if token exists and is valid
        user = await users.find_one({
            "verification_token": token
        })
        
        if not user:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"status": "invalid", "message": "Invalid verification token"}
            )
            
        # If user is already verified
        if user.get("is_verified"):
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "status": "already_verified",
                    "message": "Email is already verified"
                }
            )
            
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "pending", "message": "Token valid, verification pending"}
        )
        
    except Exception as e:
        logger.error(f"Error checking verification status: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "message": "Internal server error"}
        )

@router.post("/verify-email")
async def verify_email_endpoint(
    request: EmailVerificationRequest,
    background_tasks: BackgroundTasks
):
    try:
        token = request.token.strip()
        
        # Check if token exists
        verification = await verification_tokens.find_one({"token": token})
        
        # Check if already verified within last 2 hours
        if verification and verification.get("verified"):
            if (datetime.utcnow() - verification["created_at"]).total_seconds() <= 7200:
                return JSONResponse(
                    status_code=status.HTTP_200_OK,
                    content={
                        "success": True,
                        "status": "already_verified",
                        "message": "Email already verified"
                    }
                )
            else:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "success": False,
                        "status": "expired",
                        "message": "Verification token has expired"
                    }
                )

        # Check user
        user = await users.find_one({
            "verification_token": token,
            "created_at": {"$gt": datetime.utcnow() - timedelta(days=1)}  # 24 hour validity
        })

        if not user:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "success": False,
                    "status": "expired",
                    "message": "Invalid or expired verification token"
                }
            )

        if user.get("is_verified"):
            # Store verification status
            await verification_tokens.insert_one({
                "token": token,
                "user_id": str(user["_id"]),
                "verified": True,
                "created_at": datetime.utcnow()
            })
            
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "success": True,
                    "status": "already_verified",
                    "message": "Email already verified"
                }
            )

        # Perform verification
        result = await users.find_one_and_update(
            {
                "_id": user["_id"],
                "is_verified": False
            },
            {
                "$set": {
                    "is_verified": True,
                    "verification_token": None,
                    "email_verified": True,
                    "email_verified_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            },
            return_document=True
        )

        if result:
            # Store verification status
            await verification_tokens.insert_one({
                "token": token,
                "user_id": str(result["_id"]),
                "verified": True,
                "created_at": datetime.utcnow()
            })

            # Send success email in background
            background_tasks.add_task(
                send_verification_success_email,
                result['email'],
                result['name']
            )

            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "success": True,
                    "status": "verified",
                    "message": "Email verified successfully",
                    "user": {
                        "email": result["email"],
                        "is_verified": True
                    }
                }
            )

        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "status": "failed",
                "message": "Verification failed"
            }
        )

    except Exception as e:
        logger.error(f"Error in verify_email_endpoint: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "status": "error",
                "message": "Verification failed due to server error"
            }
        )

@router.post("/verify-email/resend", response_model=dict)
async def resend_verification_email(request: Request):
    """Resend verification email to user"""
    try:
        # Get token from header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid token"
            )

        token = auth_header.split(" ")[1]
        
        try:
            # Decode token to get user ID
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )
            user_id = payload.get("sub")
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token"
                )
        except PyJWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )

        try:
            # Get user and verify they exist
            user = await users.find_one({"_id": ObjectId(user_id)})
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )

            # Check if already verified
            if user.get("is_verified", False):
                return JSONResponse(
                    status_code=status.HTTP_200_OK,
                    content={
                        "success": True,
                        "message": "Email is already verified"
                    }
                )

            # Generate new verification token
            new_verification_token = str(uuid.uuid4())

            # First try to send the verification email
            email_sent = await send_verification_email(
                user["email"],
                user["name"],
                new_verification_token
            )

            if not email_sent:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to send verification email"
                )

            # If email sent successfully, update user with new token
            result = await users.find_one_and_update(
                {"_id": ObjectId(user_id)},
                {
                    "$set": {
                        "verification_token": new_verification_token,
                        "verification_sent_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                },
                return_document=True
            )

            if not result:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Failed to update user"
                )

            # Also cleanup any old verification tokens
            await verification_tokens.delete_many({"user_id": str(user_id)})

            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "success": True,
                    "message": "Verification email sent successfully"
                }
            )

        except Exception as e:
            logger.error(f"Error processing user: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error"
            )

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error in resend_verification: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resend verification email"
        )

async def require_verified_email(current_user=Depends(get_current_user)):
    """Middleware to ensure user's email is verified"""
    if not current_user.get("is_verified", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email address before accessing this resource"
        )
    return current_user

@router.post("/logout")
async def logout(request: Request):
    """Logout user"""
    try:
        # Get authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header"
            )
        
        # Extract token
        token = auth_header.split(" ")[1]
        
        # Add token to blacklist with TTL (24 hours)
        try:
            await blacklisted_tokens.insert_one({
                "token": token,
                "created_at": datetime.utcnow()
            })
        except Exception as e:
            if "E11000 duplicate key error" in str(e):
                # Token is already blacklisted, log and continue
                logger.warning(f"Token already blacklisted: {token}")
            else:
                logger.error(f"Error blacklisting token: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to blacklist token"
                )
        
        return {
            "message": "Successfully logged out",
            "status": "success"
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error during logout: {str(e)}")
        return {
            "message": "Logged out locally",
            "status": "success"
        }

@router.post("/refresh-token")
async def refresh_token_endpoint(request: Request):
    """Refresh access token with better error handling"""
    try:
        data = await request.json()
        refresh_token = data.get("refresh_token")
        
        if not refresh_token:
            logger.warning("No refresh token provided")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Refresh token is required"
            )

        # Verify refresh token
        try:
            payload = jwt.decode(
                refresh_token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )
        except ExpiredSignatureError:
            logger.warning("Refresh token expired")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token expired"
            )
        except (DecodeError, PyJWTError) as e:
            logger.error(f"Invalid refresh token: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token claims"
            )

        # Get user
        user = await users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )

        # Generate new tokens
        tokens = await generate_auth_tokens(user)
        return tokens

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error refreshing token: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to refresh token"
        )

# Add request tracking
_processing_codes = set()

# Update in-memory tracking with TTL
class CodeTracker:
    def __init__(self):
        self._codes = {}
        self._lock = asyncio.Lock()
        
    async def add_code(self, code: str) -> bool:
        async with self._lock:
            if code in self._codes:
                return False
            self._codes[code] = datetime.utcnow()
            return True
            
    async def cleanup(self):
        now = datetime.utcnow()
        expired = [code for code, time in self._codes.items() 
                  if now - time > timedelta(minutes=5)]
        for code in expired:
            del self._codes[code]

code_tracker = CodeTracker()

@router.post("/social/google")
async def google_auth(request: Request):
    """Handle Google OAuth login and callback"""
    try:
        data = await request.json()
        code = data.get("code")
        
        if not code:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Authorization code is required"}
            )

        # Try to add code to tracker
        if not await code_tracker.add_code(code):
            logger.info(f"Duplicate request detected for code: {code[:10]}...")
            return JSONResponse(
                status_code=409,  # Changed from 400 to 409 Conflict
                content={"success": False, "message": "Request already being processed"}
            )

        try:
            logger.info(f"Processing Google auth with code: {code[:15]}...")
            success, user_info, error = await handle_google_auth(code)
            
            if not success:
                logger.error(f"Google auth failed: {error}")
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": error}
                )

            success, result, error = await authenticate_social_user(
                provider="google",
                email=user_info["email"],
                name=user_info.get("name", user_info["email"].split("@")[0]),
                verified=True
            )

            if not success:
                logger.error(f"User authentication failed: {error}")
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": error}
                )

            logger.info(f"Successfully authenticated user: {user_info['email']}")
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "tokens": result["tokens"],
                    "user": result["user"]
                }
            )

        finally:
            # Cleanup old codes periodically
            await code_tracker.cleanup()

    except Exception as e:
        logger.error(f"Google auth error: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "Authentication failed. Please try again."
            }
        )

async def get_cached_verification(key: str) -> Optional[dict]:
    """Get cached verification result"""
    # Implement caching here (e.g., using Redis or in-memory cache)
    return None

async def cache_verification_result(key: str, result: Optional[dict]) -> None:
    """Cache verification result"""
    # Implement caching here (e.g., using Redis or in-memory cache)
    pass
