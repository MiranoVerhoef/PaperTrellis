from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from sqlmodel import SQLModel, Field
import json

class Template(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    name: str
    enabled: bool = True

    doc_type: str = "Document"
    doc_folder: str = "Inbox"

    # Stored as JSON array strings
    tags_json: str = "[]"
    match_mode: str = "all"
    match_patterns_json: str = "[]"

    company_regex: str = ""
    invoice_number_regex: str = ""
    date_regex: str = ""

    output_path_template: str = "{doc_folder}/{company}/{date:%Y}"
    filename_template: str = "{company}_{invoice_number}_{date:%Y-%m-%d}"

    created_at: datetime = Field(default_factory=datetime.utcnow)

    def tags(self) -> List[str]:
        try:
            arr = json.loads(self.tags_json or "[]")
            return [str(x).strip() for x in arr if str(x).strip()]
        except Exception:
            return []

    def set_tags(self, tags: List[str]) -> None:
        tags = [t.strip() for t in (tags or []) if t and t.strip()]
        self.tags_json = json.dumps(sorted(set(tags), key=str.lower))

    def match_patterns(self) -> List[str]:
        try:
            arr = json.loads(self.match_patterns_json or "[]")
            return [str(x) for x in arr if str(x).strip()]
        except Exception:
            return []

    def set_match_patterns(self, patterns: List[str]) -> None:
        patterns = [p.strip() for p in (patterns or []) if p and p.strip()]
        self.match_patterns_json = json.dumps(patterns)

class Job(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    source: str = "ingest"  # ingest|upload
    input_path: str = ""
    original_name: str = ""
    status: str = "failed"  # ok|failed|skipped
    message: str = ""
    template_id: Optional[int] = None
    dest_path: str = ""

    extracted_company: str = ""
    extracted_invoice_number: str = ""
    extracted_date: str = ""  # ISO

    created_at: datetime = Field(default_factory=datetime.utcnow)

class Document(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    location: str = "library"  # library|failed
    abs_path: str
    rel_path: str
    filename: str
    ext: str = ""
    status: str = "indexed"  # indexed|ok|failed|skipped

    tags_json: str = "[]"
    template_id: Optional[int] = None

    ocr_text: str = ""
    extracted_company: str = ""
    extracted_invoice_number: str = ""
    extracted_date: str = ""

    size_bytes: int = 0
    mtime: float = 0.0

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def tags(self) -> List[str]:
        try:
            arr = json.loads(self.tags_json or "[]")
            return [str(x).strip() for x in arr if str(x).strip()]
        except Exception:
            return []

    def set_tags(self, tags: List[str]) -> None:
        tags = [t.strip() for t in (tags or []) if t and t.strip()]
        self.tags_json = json.dumps(sorted(set(tags), key=str.lower))
