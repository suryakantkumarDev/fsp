from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, constr, validator
from enum import Enum
import re

class SocialProvider(str, Enum):
    GOOGLE = "google"
    LINKEDIN = "linkedin"
    NONE = "none"

class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"

class SocialAccount(BaseModel):
    provider: SocialProvider
    provider_user_id: str
    email: EmailStr
    name: Optional[str] = None

class Subscription(BaseModel):
    plan_id: str
    status: str  # active, expired, cancelled
    start_date: datetime
    end_date: datetime
    auto_renew: bool = False
    payment_id: Optional[str] = None

class User(BaseModel):
    id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex)
    name: str
    username: str
    email: EmailStr
    password_hash: Optional[str] = None
    profile_image: Optional[str] = None
    name_avatar: Optional[str] = None
    social_accounts: List[SocialAccount] = []
    role: UserRole = UserRole.USER
    subscription: Subscription
    is_active: bool = True
    is_verified: bool = False
    verification_token: Optional[str] = None
    password_reset_token: Optional[str] = None
    password_reset_expires: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class UserCreate(BaseModel):
    name: constr(min_length=2, max_length=50)  # Full name
    email: EmailStr
    password: constr(min_length=6)
    phone: Optional[str] = None

    @validator('phone')
    def validate_phone(cls, v):
        if v:
            # Basic phone validation - can be enhanced
            cleaned = ''.join(filter(str.isdigit, v))
            if len(cleaned) < 10:
                raise ValueError('Phone number must have at least 10 digits')
            return cleaned
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "name": "John Doe",
                "email": "john@example.com",
                "password": "securepass123",
                "phone": "1234567890"
            }
        }

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserSocialLogin(BaseModel):
    provider: SocialProvider
    token: str

class UserPasswordReset(BaseModel):
    email: EmailStr

class UserPasswordChange(BaseModel):
    old_password: str
    new_password: str

class UserPasswordUpdate(BaseModel):
    token: str
    new_password: str

class UserProfileUpdate(BaseModel):
    name: Optional[str] = None
    username: Optional[str] = None
    profile_image: Optional[str] = None  # Base64 image

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    
class UserResponse(BaseModel):
    id: str
    name: str
    username: str
    email: str
    profile_image: Optional[str] = None
    name_avatar: Optional[str] = None
    role: str
    subscription: Dict[str, Any]
    is_verified: bool
    created_at: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

def user_db_to_response(user: dict) -> dict:
    """
    Convert user from database format to response format
    """
    return {
        "id": str(user.get("_id", "")),
        "name": user.get("name", ""),
        "username": user.get("username", ""),
        "email": user.get("email", ""),
        "profile_image": user.get("profile_image"),
        "name_avatar": user.get("name_avatar"),
        "role": user.get("role", "user"),
        "subscription": user.get("subscription", {}),
        "is_verified": user.get("is_verified", False),
        "created_at": user.get("created_at", datetime.utcnow())
    }