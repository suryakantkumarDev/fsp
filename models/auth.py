from pydantic import BaseModel, EmailStr, constr, Field, validator
from typing import Optional

class SocialLoginInput(BaseModel):
    provider: str
    provider_user_id: str
    email: EmailStr
    name: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordReset(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)

class PasswordResetResponse(BaseModel):
    message: str
    success: bool

class EmailVerificationRequest(BaseModel):
    token: str

    @validator('token')
    def validate_token(cls, v):
        if not v or not isinstance(v, str):
            raise ValueError('Invalid token format')
        return v.strip()

class EmailVerificationResponse(BaseModel):
    message: str
    success: bool
    user: Optional[dict] = None  # Make user optional
