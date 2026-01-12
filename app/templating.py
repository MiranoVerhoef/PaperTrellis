from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple
from dateutil import parser as dateparser

from .models import Template
from .utils import safe_filename

@dataclass
class Extracted:
    company: str = ""
    invoice_number: str = ""
    date: Optional[datetime] = None

def _first_match(pattern: str, text: str) -> str:
    try:
        m = re.search(pattern, text)
    except re.error:
        return ""
    if not m:
        return ""
    if m.groups():
        return (m.group(1) or "").strip()
    return (m.group(0) or "").strip()

def evaluate_template(tpl: Template, text: str) -> Tuple[bool, int]:
    patterns = tpl.match_patterns or []
    if not patterns:
        return True, 0

    hits = 0
    for p in patterns:
        try:
            if re.search(p, text, re.IGNORECASE | re.MULTILINE):
                hits += 1
        except re.error:
            # Treat invalid regex as non-hit
            continue

    if tpl.match_mode.lower() == "any":
        return hits > 0, hits
    # default all
    return hits == len(patterns), hits

def extract_fields(tpl: Template, text: str) -> Extracted:
    company = _first_match(tpl.company_regex, text)
    inv = _first_match(tpl.invoice_number_regex, text)
    date_raw = _first_match(tpl.date_regex, text)

    dt = None
    if date_raw:
        try:
            dt = dateparser.parse(date_raw, dayfirst=False, fuzzy=True)
        except Exception:
            dt = None

    company = safe_filename(company) if company else ""
    inv = safe_filename(inv) if inv else ""
    return Extracted(company=company, invoice_number=inv, date=dt)

def format_path_and_name(
    tpl: Template,
    extracted: Extracted,
    original_name: str,
    ext: str
) -> Tuple[str, str]:
    date_val = extracted.date or datetime.utcnow()

    ctx = {
        "doc_folder": tpl.doc_folder,
        "doc_type": tpl.doc_folder,
        "company": extracted.company or "UnknownCompany",
        "invoice_number": extracted.invoice_number or "UnknownInvoice",
        "date": date_val,
        "ext": ext.lstrip("."),
        "original_name": original_name,
    }

    # Build path (relative) and filename (no ext)
    out_rel = tpl.output_path_template.format(**ctx).strip().strip("/")
    fname = tpl.filename_template.format(**ctx).strip()
    fname = safe_filename(fname) if fname else safe_filename(original_name)

    return out_rel, fname
