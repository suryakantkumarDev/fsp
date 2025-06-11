from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from pymongo.errors import DuplicateKeyError
import bcrypt  # Add bcrypt import
from config import settings
from utils.password_utils import get_password_hash, verify_password
from utils.token_utils import create_access_token, create_refresh_token
from utils.helpers import generate_unique_id, generate_name_avatar
from models.subscription import SubscriptionStatus
from models.database import users as users_collection, get_database
import uuid
from jwt import PyJWTError  # Changed from jose.JWTError
import logging
from passlib.context import CryptContext

logger = logging.getLogger(__name__)

# Password hashing configuration
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt"""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)

# Create indexes
async def setup_db_indexes():
    await users_collection.create_index("email", unique=True)
    await users_collection.create_index("username", unique=True)
    
    # Index for social accounts
    await users_collection.create_index([
        ("social_accounts.provider", 1),
        ("social_accounts.provider_user_id", 1)
    ])

async def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Get a user by email"""
    return await users_collection.find_one({"email": email})

async def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """Get a user by username"""
    return await users_collection.find_one({"username": username})

async def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """Get a user by ID"""
    return await users_collection.find_one({"_id": user_id})

async def get_user_by_reset_token(token: str) -> Optional[Dict[str, Any]]:
    """Get a user by password reset token"""
    return await users_collection.find_one({
        "password_reset_token": token,
        "password_reset_expires": {"$gt": datetime.utcnow()}
    })

async def get_user_by_social_provider(provider: str, provider_user_id: str) -> Optional[Dict[str, Any]]:
    """Get a user by social provider information"""
    return await users_collection.find_one({
        "social_accounts.provider": provider,
        "social_accounts.provider_user_id": provider_user_id
    })

async def create_user(
    username: str,
    email: str,
    password: str,
    name: str = None,
    phone: str = None,
    verification_token: str = None
) -> Optional[Dict[str, Any]]:
    """Create a new user"""
    try:
        # Check if user exists
        existing_user = await users_collection.find_one({"email": email})
        if (existing_user):
            logger.warning(f"User with email {email} already exists")
            return None

        # Create user document with minimum required fields
        user = {
            "username": username,
            "email": email,
            "password_hash": get_password_hash(password),  # Use helper function
            "name": name or username,
            "is_verified": False,
            "verification_token": verification_token or str(uuid.uuid4()),
            "role": "user",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        # Add optional fields if provided
        if phone:
            user["phone"] = phone

        # Insert into database
        result = await users_collection.insert_one(user)
        if not result.inserted_id:
            logger.error("Failed to insert user into database")
            return None

        # Return user without password
        user["_id"] = result.inserted_id
        del user["password_hash"]
        logger.info(f"Successfully created user with email: {email}")
        return user

    except Exception as e:
        logger.error(f"Error creating user: {str(e)}", exc_info=True)
        return None

async def authenticate_user(email: str, password: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """
    Authenticate a user with email and password
    Returns (success, user_data, error_message)
    """
    user = await get_user_by_email(email)
    
    if not user:
        return False, None, "Invalid email or password"
    
    if not user.get("password_hash"):
        return False, None, "Please login with your social account"
    
    if not verify_password(password, user["password_hash"]):
        return False, None, "Invalid email or password"
    
    if not user.get("is_active", True):
        return False, None, "Account is disabled"
    
    return True, user, ""

async def generate_auth_tokens(user: dict) -> dict:
    """Generate access and refresh tokens for user"""
    token_data = {"sub": str(user["_id"])}  # Ensure user ID is converted to string
    
    # Generate tokens
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    
    # Include user data in response
    user_data = {
        "id": str(user["_id"]),
        "name": user.get("name", ""),
        "email": user.get("email", ""),
        "is_verified": user.get("is_verified", False),
        "profile_image": user.get("profile_image"),
        "name_avatar": user.get("name_avatar")
    }
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user_data
    }

async def create_password_reset_token(email: str) -> Tuple[bool, str, str]:
    """
    Create a password reset token for a user
    Returns (success, token, error_message)
    """
    user = await get_user_by_email(email)
    
    if not user:
        # Don't reveal that the email doesn't exist
        return False, "", "If your email is registered, you will receive a password reset link"
    
    if not user.get("password_hash"):
        return False, "", "Social login accounts cannot use password reset"
    
    # Generate reset token
    reset_token = str(uuid.uuid4())
    expires = datetime.utcnow() + timedelta(hours=1)
    
    # Update user with reset token
    await users_collection.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "password_reset_token": reset_token,
                "password_reset_expires": expires,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    return True, reset_token, ""

async def reset_password(token: str, new_password: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Reset a user's password using a token
    Returns (success, error_message, user_data)
    """
    user = await get_user_by_reset_token(token)
    
    if not user:
        return False, "Invalid or expired token", None
    
    try:
        # Update password and clear reset token
        result = await users_collection.find_one_and_update(
            {"_id": user["_id"]},
            {
                "$set": {
                    "password_hash": get_password_hash(new_password),
                    "password_reset_token": None,
                    "password_reset_expires": None,
                    "updated_at": datetime.utcnow()
                }
            },
            return_document=True
        )
        
        return True, "", result
    except Exception as e:
        logger.error(f"Error resetting password: {str(e)}")
        return False, "Failed to reset password", None

async def change_password(user_id: str, old_password: str, new_password: str) -> Tuple[bool, str]:
    """
    Change a user's password
    Returns (success, error_message)
    """
    user = await get_user_by_id(user_id)
    
    if not user:
        return False, "User not found"
    
    if not user.get("password_hash"):
        return False, "Social login accounts cannot change password"
    
    if not verify_password(old_password, user["password_hash"]):
        return False, "Current password is incorrect"
    
    # Update password
    await users_collection.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "password_hash": get_password_hash(new_password),"updated_at": datetime.utcnow()
            }
        }
    )
    
    return True, ""

async def verify_email(token: str) -> bool:
    try:
        logger.info(f"Starting email verification with token: {token}")
        
        token = token.strip()
        if not token:
            logger.error("Empty token received")
            return False

        # Use atomic update operation
        result = await users_collection.find_one_and_update(
            {
                "verification_token": token,
                "$or": [
                    {"is_verified": {"$ne": True}},
                    {"email_verified": {"$ne": True}}
                ]
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
            logger.info(f"Successfully verified email for user: {result['email']}")
            return True
            
        logger.error(f"No user found with verification token: {token}")
        return False
        
    except Exception as e:
        logger.error(f"Error in verify_email: {str(e)}", exc_info=True)
        return False

async def authenticate_social_user(provider: str, email: str, name: str, verified: bool = False) -> Tuple[bool, Dict[str, Any], str]:
    """Authenticate or create a user via social login"""
    try:
        if not email:
            logger.error("Missing email from social login")
            return False, None, "Email is required"

        # Clean up name
        cleaned_name = name.split("@")[0] if "@" in name else name
        username = email.split("@")[0]

        # Find existing user
        user = await users_collection.find_one({"email": email})
        
        if user:
            # Update existing user
            update_data = {
                "last_login": datetime.utcnow(),
                f"social_logins.{provider}": True,
                "updated_at": datetime.utcnow()
            }

            # Update name if not set
            if not user.get("name"):
                update_data["name"] = cleaned_name

            # Generate avatar if needed
            if not user.get("name_avatar"):
                update_data["name_avatar"] = generate_name_avatar(cleaned_name)

            result = await users_collection.find_one_and_update(
                {"_id": user["_id"]},
                {"$set": update_data},
                return_document=True
            )
        else:
            # Create new user
            user = {
                "email": email,
                "name": cleaned_name,
                "username": username,
                "name_avatar": generate_name_avatar(cleaned_name),
                "is_verified": verified,
                "social_logins": {provider: True},
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "last_login": datetime.utcnow(),
                "role": "user"
            }
            result = await users_collection.insert_one(user)
            user["_id"] = result.inserted_id

        # Generate tokens
        tokens = await generate_auth_tokens(user)
        
        return True, {
            "tokens": tokens,
            "user": {
                "id": str(user["_id"]),
                "email": user["email"],
                "name": user.get("name", cleaned_name),
                "username": user.get("username", username),
                "name_avatar": user.get("name_avatar"),
                "is_verified": user.get("is_verified", verified)
            }
        }, ""

    except Exception as e:
        logger.error(f"Social auth error: {str(e)}", exc_info=True)
        return False, None, "Authentication failed. Please try again."