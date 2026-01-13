from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, case_sensitive=False)

    ingest_dir: str = Field(default="/data/ingest", alias="ODM_INGEST_DIR")
    library_dir: str = Field(default="/data/library", alias="ODM_LIBRARY_DIR")
    config_dir: str = Field(default="/data/config", alias="ODM_CONFIG_DIR")
    failed_dir: str = Field(default="/data/failed", alias="ODM_FAILED_DIR")
    tmp_dir: str = Field(default="/data/tmp", alias="ODM_TMP_DIR")

    scan_enabled: bool = Field(default=True, alias="ODM_SCAN_ENABLED")
    scan_interval_seconds: int = Field(default=15, alias="ODM_SCAN_INTERVAL_SECONDS")
    tesseract_lang: str = Field(default="eng", alias="ODM_TESSERACT_LANG")

    auth_enabled: bool = Field(default=True, alias="ODM_AUTH_ENABLED")
    admin_password: str = Field(default="", alias="ODM_ADMIN_PASSWORD")
    session_secret: str = Field(default="", alias="ODM_SESSION_SECRET")

settings = Settings()
