"""
Configuration module using Pydantic BaseSettings
Loads all environment variables and provides type-safe config access
"""

from pydantic_settings import BaseSettings
from typing import List


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
    MAIL_HOST: str = "smtp.gmail.com"
    MAIL_PORT: int = 587
    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_ENCRYPTION: str = "tls"
    MAIL_FROM_ADDRESS: str = ""
    MAIL_FROM_NAME: str = "CricGeo"
    MAIL_BRAND_NAME: str = "CricGeo"
    MAIL_LOGO_URL: str = ""
    
    # Frontend URL
    FRONTEND_URL: str = "http://127.0.0.1:8000/"
    
    # Google OAuth2 Configuration
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/google/callback"
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


# Global settings instance
settings = Settings()
