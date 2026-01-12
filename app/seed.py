from __future__ import annotations

from sqlmodel import select

from .db import get_session
from .models import Template, AppConfig

def seed_defaults() -> None:
    with get_session() as s:
        # Seed config keys if missing
        for k, v in {
            "ingest_dir": "",
            "library_dir": "",
            "scan_enabled": "",
            "scan_interval_seconds": "",
            "tesseract_lang": "",
        }.items():
            if not s.get(AppConfig, k):
                s.add(AppConfig(key=k, value=v))
        s.commit()

        # Seed an example invoice template if none exist
        existing = s.exec(select(Template)).first()
        if existing:
            return

        s.add(Template(
            name="Default Invoice",
            enabled=True,
            doc_folder="Invoices",
            match_mode="any",
            match_patterns=[
                r"\binvoice\b",
                r"\bfactu(?:ur|ra)\b",   # Dutch
                r"\brechnung\b",         # German
            ],
            company_regex=r"(?im)^(?:seller|vendor|company|from|leverancier)\s*[:\-]\s*(.+)$",
            invoice_number_regex=r"(?im)(?:invoice|factu(?:ur|ra)|rekening)\s*(?:no|number|nr|nummer)?\.?\s*[:\-]?\s*([A-Z0-9\-\/]+)",
            date_regex=r"(?im)(?:date|datum)\s*[:\-]?\s*([0-9]{4}[-/][0-9]{1,2}[-/][0-9]{1,2}|[0-9]{1,2}[-/][0-9]{1,2}[-/][0-9]{2,4})",
            output_path_template="{doc_folder}/{company}/{date:%Y}",
            filename_template="{company}_{invoice_number}_{date:%Y-%m-%d}"
        ))
        s.commit()
