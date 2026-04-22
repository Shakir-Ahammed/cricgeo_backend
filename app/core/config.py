"""
Configuration module using Pydantic BaseSettings
Loads all environment variables and provides type-safe config access
"""

from pydantic_settings import BaseSettings
from typing import List
from pydantic import Field, AliasChoices


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables
    """
    
    # Application
    APP_NAME: str = "CricGeo Backend"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # Database Configuration
    # Supports multiple database engines through connection string
    # Examples:
    #   PostgreSQL: postgresql+asyncpg://user:pass@host:5432/dbname
    #   MySQL:      mysql+aiomysql://root:password@localhost:3306/dbname
    #   SQLite:     sqlite+aiosqlite:///./test.db
    DATABASE_URL: str
    
    # JWT Configuration
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 10080  # 7 days
    
    # CORS Configuration
    CORS_ORIGINS: List[str] = ["*"]
    
    # Pagination
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100
    
    # Email Configuration
    MAIL_HOST: str = Field(
        default="smtp-relay.brevo.com",
        validation_alias=AliasChoices("MAIL_HOST", "SMTP_HOST"),
    )
    MAIL_PORT: int = Field(
        default=587,
        validation_alias=AliasChoices("MAIL_PORT", "SMTP_PORT"),
    )
    MAIL_USERNAME: str = Field(
        default="7809f9001@smtp-brevo.com",
        validation_alias=AliasChoices("MAIL_USERNAME", "SMTP_USERNAME"),
    )
    MAIL_PASSWORD: str = Field(
        default="hmOGg9Ux0RqCNFMS",
        validation_alias=AliasChoices("MAIL_PASSWORD", "SMTP_PASSWORD"),
    )
    MAIL_ENCRYPTION: str = Field(
        default="tls",
        validation_alias=AliasChoices("MAIL_ENCRYPTION", "SMTP_ENCRYPTION"),
    )
    MAIL_FROM_ADDRESS: str = "noreply@progotibarta.com"
    MAIL_FROM_NAME: str = "CricGeo"
    MAIL_BRAND_NAME: str = "CricGeo"
    MAIL_LOGO_URL: str = ""

    # Bulk SMS Configuration
    BULKSMS_API_KEY: str = "dBG4rYOLWW28f3ip15yW"
    BULKSMS_SENDER_ID: str = "8809617624082"
    BULKSMS_API_URL: str = "http://bulksmsbd.net/api/smsapi"
    
    # Frontend URL
    FRONTEND_URL: str = "http://127.0.0.1:8000/"
    
    # Google OAuth2 Configuration
    GOOGLE_CLIENT_ID: str = "1008567724778-bqi9vv207211ctogf213mm5uo3gnhk5r.apps.googleusercontent.com"
    GOOGLE_CLIENT_SECRET: str = "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"
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/google/callback"
    # Mobile client IDs — set these to allow id_token verification from Android/iOS apps
    GOOGLE_ANDROID_CLIENT_ID: str = "1008567724778-7tll0fkhhs4as3lmf0rgmuvd10df80lq.apps.googleusercontent.com"

    # Cloudflare R2 Object Storage
    # Endpoint: https://<account_id>.r2.cloudflarestorage.com
    STORAGE_ENDPOINT: str = "https://0aa57640242268baadff5c1238805c95.r2.cloudflarestorage.com"
    STORAGE_BUCKET: str = "cricgeo"
    STORAGE_ACCESS_KEY_ID: str = "b3308ac3a7b1c2a03b5e6e70925925f7"
    STORAGE_SECRET_ACCESS_KEY: str = "d0ec507691349507f589bb6ef9586de8ff9730381a8266dc1e81f8a49c86cde3"
    # Public URL base — set this to your custom domain or R2.dev public URL
    # e.g. https://pub-XXXX.r2.dev  OR  https://files.yourdomain.com
    STORAGE_PUBLIC_URL: str = "https://0aa57640242268baadff5c1238805c95.r2.cloudflarestorage.com/cricgeo"
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


# Global settings instance
settings = Settings()
