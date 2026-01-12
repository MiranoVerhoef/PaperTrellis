from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ODM_", case_sensitive=False)

    data_dir: str = "/data"
    config_dir: str = "/data/config"
    ingest_dir: str = "/data/ingest"
    library_dir: str = "/data/library"

    failed_dir: str = "/data/failed"
    tmp_dir: str = "/data/tmp"

    scan_enabled: bool = True
    scan_interval_seconds: int = 15

    # Tesseract language(s), e.g. "eng" or "eng+deu+nld"
    tesseract_lang: str = "eng"

    # If PDFs already have text, we don't OCR unless extracted text length is below this threshold
    pdf_text_min_chars: int = 25

settings = Settings()
