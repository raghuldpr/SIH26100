from pathlib import Path
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base directory for document-engine service and root repository
SERVICE_DIR = Path(__file__).resolve().parent.parent.parent
REPO_ROOT = SERVICE_DIR.parent
ENV_FILES = (
    str(SERVICE_DIR / ".env"),
    str(REPO_ROOT / ".env"),
    ".env",
)


class Settings(BaseSettings):
    """Application configuration loaded from environment variables and .env file."""

    APP_NAME: str = "SIH26100 Document Engine"
    APP_ENV: str = "development"
    PROJECT_DESCRIPTION: str = (
        "Deterministic Document Engine & OCR Service for SIH26100 GeM procurement compliance platform"
    )
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"

    # Server binding
    HOST: str = "0.0.0.0"
    PORT: int = 8001

    # CORS configuration
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    # Logging
    LOG_LEVEL: str = "INFO"

    # Document storage & processing
    TEMP_DIR: str = "temp"
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: List[str] = [".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if not v or v.strip() == "":
                return []
            if v.strip() == "*":
                return ["*"]
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return [str(i).strip() for i in v if str(i).strip()]
        return []

    @property
    def temp_path(self) -> Path:
        """Returns resolved Path to scratch temp directory."""
        path = Path(self.TEMP_DIR)
        if not path.is_absolute():
            path = SERVICE_DIR / path
        path.mkdir(parents=True, exist_ok=True)
        return path

    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
