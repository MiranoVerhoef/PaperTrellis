from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, date
from typing import Tuple, Optional, Dict, Any

from dateutil import parser as dateparser

from .models import Template
from .utils import safe_filename

@dataclass
class Extracted:
    company: str = ""
    invoice_number: str = ""
    date: Optional[date] = None
    doc_type: str = "Document"
    doc_folder: str = "Inbox"

def evaluate_template(tpl: Template, text: str) -> Tuple[bool, int]:
    pats = tpl.match_patterns()
    if not pats:
        return False, 0
    flags = re.IGNORECASE | re.MULTILINE
    hits = 0
    for p in pats:
        try:
            if re.search(p, text, flags=flags):
                hits += 1
        except re.error:
            # ignore invalid regex in score
            pass

    if tpl.match_mode == "any":
        return (hits > 0), hits
    return (hits == len(pats)), hits

def _first_group(regex: str, text: str) -> str:
    if not regex:
        return ""
    try:
        m = re.search(regex, text, flags=re.IGNORECASE | re.MULTILINE)
        if not m:
            return ""
        if m.groups():
            return (m.group(1) or "").strip()
        return (m.group(0) or "").strip()
    except re.error:
        return ""

def _parse_date(s: str) -> Optional[date]:
    s = (s or "").strip()
    if not s:
        return None
    # Prefer day-first for EU invoices
    try:
        dt = dateparser.parse(s, dayfirst=True, fuzzy=True)
        if not dt:
            return None
        return dt.date()
    except Exception:
        return None

def extract_fields(tpl: Template, text: str) -> Extracted:
    company = _first_group(tpl.company_regex, text)
    inv = _first_group(tpl.invoice_number_regex, text)
    d = _parse_date(_first_group(tpl.date_regex, text))
    return Extracted(
        company=company,
        invoice_number=inv,
        date=d,
        doc_type=tpl.doc_type or "Document",
        doc_folder=tpl.doc_folder or "Inbox",
    )

def _fmt_date(dt: Optional[date], fmt: str) -> str:
    if not dt:
        return ""
    return datetime(dt.year, dt.month, dt.day).strftime(fmt)

def _format_with_date_vars(t: str, vars: Dict[str, Any]) -> str:
    # supports {date:%Y-%m-%d}
    def repl(m: re.Match) -> str:
        key = m.group(1)
        fmt = m.group(2)
        if key == "date":
            return _fmt_date(vars.get("date"), fmt or "%Y-%m-%d")
        # fallback
        val = vars.get(key, "")
        return str(val) if val is not None else ""
    # {var:%Y} or {var}
    pattern = re.compile(r"\{([a-zA-Z_]+)(?::([^}]+))?\}")
    return pattern.sub(repl, t)

def format_path_and_name(
    tpl: Template,
    extracted: Extracted,
    original_stem: str,
    ext: str
) -> Tuple[str, str]:
    vars: Dict[str, Any] = {
        "doc_folder": extracted.doc_folder,
        "doc_type": extracted.doc_type,
        "company": extracted.company,
        "invoice_number": extracted.invoice_number,
        "date": extracted.date,
        "original_name": original_stem,
    }

    out_path = _format_with_date_vars(tpl.output_path_template or "{doc_folder}", vars)
    out_name = _format_with_date_vars(tpl.filename_template or "{original_name}", vars)

    # sanitize parts
    out_path = out_path.strip().strip("/").strip()
    out_name = safe_filename(out_name.strip())

    # normalize slashes
    out_path = out_path.replace("\\", "/")
    out_path = "/".join([safe_filename(p) for p in out_path.split("/") if p.strip()])

    if not out_path:
        out_path = safe_filename(extracted.doc_folder or "Inbox")

    if not out_name:
        out_name = safe_filename(original_stem)

    return out_path, out_name
