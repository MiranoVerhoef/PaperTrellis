from __future__ import annotations

from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field, Column, JSON

class AppConfig(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str

class Template(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    enabled: bool = True

    # Storage folder (relative to library root), e.g. "Invoices"
    doc_folder: str = "Invoices"

    # "all" => all match patterns must appear, "any" => any one is enough
    match_mode: str = "all"
    # list[str] stored as JSON
    match_patterns: list[str] = Field(default_factory=list, sa_column=Column(JSON))

    # regex patterns for field extraction
    company_regex: str = r"(?im)^(?:seller|vendor|company)\s*[:\-]\s*(.+)$"
    invoice_number_regex: str = r"(?im)invoice\s*(?:no|number|nr)\.?\s*[:\-]?\s*([A-Z0-9\-\/]+)"
    date_regex: str = r"(?im)date\s*[:\-]?\s*([0-9]{4}[-/][0-9]{1,2}[-/][0-9]{1,2}|[0-9]{1,2}[-/][0-9]{1,2}[-/][0-9]{2,4})"

    # Jinja-ish-ish simple python .format template:
    # available vars: doc_type, company, invoice_number, date (datetime), ext, original_name
    output_path_template: str = "{doc_folder}/{company}"
    filename_template: str = "{company}_{invoice_number}_{date:%Y-%m-%d}"

class Job(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)

    source: str  # "upload" or "ingest"
    input_path: str
    original_name: str
    status: str  # "ok" | "skipped" | "failed"
    message: str = ""

    template_id: Optional[int] = Field(default=None, index=True)
    doc_folder: str = ""
    dest_path: str = ""

    extracted_company: str = ""
    extracted_invoice_number: str = ""
    extracted_date: str = ""
