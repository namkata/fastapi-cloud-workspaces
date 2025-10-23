"""
Application configuration management using Pydantic Settings.
"""
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Application Settings
    app_name: str = Field(default="FastAPI Cloud Workspaces", alias="APP_NAME")
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")
    app_description: str = Field(default="FastAPI Cloud Workspaces Application", alias="APP_DESCRIPTION")
    debug: bool = Field(default=False, alias="DEBUG")
    environment: str = Field(default="production", alias="ENVIRONMENT")

    # Server Settings
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")

    # Database Settings
    database_url: str = Field(alias="DATABASE_URL")
    database_host: str = Field(default="localhost", alias="DATABASE_HOST")
    database_port: int = Field(default=5432, alias="DATABASE_PORT")
    database_name: str = Field(default="fastapi_db", alias="DATABASE_NAME")
    database_user: str = Field(default="postgres", alias="DATABASE_USER")
    database_password: str = Field(alias="DATABASE_PASSWORD")

    # Redis Settings
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_db: int = Field(default=0, alias="REDIS_DB")

    # Security Settings
    secret_key: str = Field(alias="SECRET_KEY")
    algorithm: str = Field(default="HS256", alias="ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=7, alias="REFRESH_TOKEN_EXPIRE_DAYS")

    # CORS and Security
    allowed_origins: list[str] = Field(default=["http://localhost:3000", "http://localhost:8000"], alias="ALLOWED_ORIGINS")
    allowed_hosts: list[str] = Field(default=["localhost", "127.0.0.1"], alias="ALLOWED_HOSTS")

    # Email Settings
    smtp_server: str = Field(default="localhost", alias="SMTP_SERVER")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_username: str = Field(default="", alias="SMTP_USERNAME")
    smtp_password: str = Field(default="", alias="SMTP_PASSWORD")
    smtp_use_tls: bool = Field(default=True, alias="SMTP_USE_TLS")
    from_email: str = Field(default="noreply@example.com", alias="FROM_EMAIL")

    # Storage Settings
    storage_provider: str = Field(default="minio", alias="STORAGE_PROVIDER")  # "minio" or "s3"
    storage_max_file_size: int = Field(default=100 * 1024 * 1024, alias="STORAGE_MAX_FILE_SIZE")  # 100MB
    storage_allowed_extensions: str = Field(
        default="jpg,jpeg,png,gif,pdf,doc,docx,txt,csv,xlsx,zip,tar,gz",
        alias="STORAGE_ALLOWED_EXTENSIONS"
    )
    storage_default_quota_gb: int = Field(default=10, alias="STORAGE_DEFAULT_QUOTA_GB")  # 10GB per workspace
    UPLOAD_DIR: str = Field(default="uploads", alias="UPLOAD_DIR")  # Local upload directory

    # MinIO Settings
    minio_endpoint: str = Field(default="localhost:9000", alias="MINIO_ENDPOINT")
    minio_access_key: str = Field(default="minioadmin", alias="MINIO_ACCESS_KEY")
    minio_secret_key: str = Field(default="minioadmin", alias="MINIO_SECRET_KEY")
    minio_bucket_name: str = Field(default="workspaces", alias="MINIO_BUCKET_NAME")
    minio_secure: bool = Field(default=False, alias="MINIO_SECURE")
    minio_region: Optional[str] = Field(default=None, alias="MINIO_REGION")

    # AWS S3 Settings
    s3_bucket_name: str = Field(default="workspaces", alias="S3_BUCKET_NAME")
    aws_access_key_id: Optional[str] = Field(default=None, alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: Optional[str] = Field(default=None, alias="AWS_SECRET_ACCESS_KEY")
    aws_region: str = Field(default="us-east-1", alias="AWS_REGION")
    s3_endpoint_url: Optional[str] = Field(default=None, alias="S3_ENDPOINT_URL")  # For S3-compatible services

    # Signed URL Settings
    signed_url_expire_minutes: int = Field(default=60, alias="SIGNED_URL_EXPIRE_MINUTES")  # 1 hour

    # Logging Settings
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: str = Field(default="json", alias="LOG_FORMAT")

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment.lower() == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()


# Global settings instance
settings = get_settings()
