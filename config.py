from pathlib import Path
from typing import List, Optional
import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, ValidationInfo  # Add these imports
from functools import lru_cache
import logging

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    # Base directory and application settings
    BASE_DIR: Path = Path(__file__).resolve().parent
    APP_NAME: str = "FSP2 Backend"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    API_VERSION: str = "v1"

    # Email settings
    EMAIL_TEMPLATES_DIR: Path = BASE_DIR / "templates" / "email"
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")  # App password for Gmail
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "")
    EMAIL_FROM_NAME: str = os.getenv("EMAIL_FROM_NAME", "")
    EMAIL_USE_TLS: bool = True  # Always use TLS for Gmail
    EMAIL_SSL: bool = False
    EMAIL_TIMEOUT: int = 30
    # Removed duplicate DEBUG setting

    @field_validator('SMTP_USERNAME', 'SMTP_PASSWORD', 'EMAIL_FROM')
    @classmethod
    def validate_email_settings(cls, v: str, info: ValidationInfo) -> str:
        """Validate email-related settings"""
        if not v and info.data.get('SMTP_SERVER') == 'smtp.gmail.com':
            logger.warning(f"Missing {info.field_name} for Gmail configuration")
            return v
        return v.strip() if v else v

    def verify_email_settings(self) -> bool:
        """Verify all required email settings are configured"""
        required_settings = [
            self.SMTP_SERVER,
            self.SMTP_PORT,
            self.SMTP_USERNAME,
            self.SMTP_PASSWORD,
            self.EMAIL_FROM
        ]
        is_valid = all(required_settings)
        if not is_valid:
            logger.warning("Some required email settings are missing")
        return is_valid

    # Company details
    COMPANY_NAME: str = os.getenv("COMPANY_NAME", "Profact Inc.")
    COMPANY_ADDRESS: str = os.getenv("COMPANY_ADDRESS", "123 Business Street")
    LOGO_URL: str = os.getenv("LOGO_URL", "")

    # Frontend URL
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")

    # MongoDB settings
    MONGODB_URL: str = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    DB_NAME: str = os.getenv("DB_NAME", "profact_db")

    # JWT settings
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-secret-key")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

    # Azure Storage
    AZURE_STORAGE_CONNECTION_STRING: str = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
    AZURE_STORAGE_CONTAINER: str = os.getenv("AZURE_STORAGE_CONTAINER", "profact")
    AZURE_STORAGE_URL: str = os.getenv("AZURE_STORAGE_URL", "")

    # Payment settings
    STRIPE_PUBLIC_KEY: str = os.getenv("STRIPE_PUBLIC_KEY", "")
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    RAZORPAY_KEY_ID: str = os.getenv("RAZORPAY_KEY_ID", "")
    RAZORPAY_KEY_SECRET: str = os.getenv("RAZORPAY_KEY_SECRET", "")
    RAZORPAY_WEBHOOK_SECRET: str = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")

    # Redis settings
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))

    # Update CORS settings to be more comprehensive
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000",
    ]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = [
        "GET",
        "POST",
        "PUT",
        "DELETE",
        "PATCH",
        "OPTIONS"
    ]
    CORS_ALLOW_HEADERS: List[str] = [
        "Content-Type",
        "Authorization",
        "Access-Control-Allow-Headers",
        "Access-Control-Allow-Methods",
        "Access-Control-Allow-Origin",
        "Accept",
        "Origin",
        "X-Requested-With"
    ]

    # Subscription settings
    FREE_PLAN_ID: str = "free"
    DEFAULT_SUBSCRIPTION_DAYS: int = 30

    # File upload settings
    MAX_PROFILE_IMAGE_SIZE: int = int(os.getenv("MAX_PROFILE_IMAGE_SIZE", str(5 * 1024 * 1024)))  # Default 5MB
    ALLOWED_IMAGE_TYPES: List[str] = [
        "image/jpeg", 
        "image/png", 
        "image/gif",
        "image/svg+xml",
        "image/webp"
    ]
    UPLOAD_DIR: Path = BASE_DIR / "uploads"

    # Currency settings
    DEFAULT_CURRENCY: str = "USD"
    SUPPORTED_CURRENCIES: List[str] = ["USD", "INR", "EUR", "GBP"]

    # Google OAuth settings
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI: str = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:5173/auth/callback")
    GOOGLE_SCOPES: List[str] = ["openid", "email", "profile"]

    # LinkedIn OAuth settings
    LINKEDIN_CLIENT_ID: str = os.getenv("LINKEDIN_CLIENT_ID", "")
    LINKEDIN_CLIENT_SECRET: str = os.getenv("LINKEDIN_CLIENT_SECRET", "")
    LINKEDIN_REDIRECT_URI: str = os.getenv("LINKEDIN_REDIRECT_URI", "http://localhost:5173/auth/linkedin/callback")
    LINKEDIN_SCOPES: List[str] = ["r_liteprofile", "r_emailaddress"]

    def __init__(self):
        super().__init__()
        # Ensure template directory exists
        self.EMAIL_TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(f"Email templates directory: {self.EMAIL_TEMPLATES_DIR}")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        validate_assignment=True,
        extra='ignore'  # Add this to ignore extra env vars
    )

@lru_cache
def get_settings() -> Settings:
    """
    Create cached instance of settings
    Returns:
        Settings: Application settings
    """
    return Settings()

# Create settings instance
settings = get_settings()

# Export commonly used paths
TEMPLATES_DIR = settings.EMAIL_TEMPLATES_DIR
UPLOAD_DIR = settings.UPLOAD_DIR

# Ensure required directories exist
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)