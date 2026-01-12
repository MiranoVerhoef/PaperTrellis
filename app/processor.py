from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from sqlmodel import select

from .db import get_session
from .models import Template, Job
from .ocr import get_text
from .templating import evaluate_template, extract_fields, format_path_and_name
from .settings import settings
from .utils import atomic_move

SUPPORTED_EXTS = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}

def _choose_template(text: str) -> Optional[Template]:
    with get_session() as s:
        templates = s.exec(select(Template).where(Template.enabled == True)).all()  # noqa: E712
        best = None
        best_score = -1
        for tpl in templates:
            ok, score = evaluate_template(tpl, text)
            if ok and score >= best_score:
                best = tpl
                best_score = score
        return best

def _ingest_relative_subdir(path: str) -> str:
    """If path is under ingest_dir, return its relative parent folder ('' if none)."""
    try:
        ingest_root = os.path.abspath(settings.ingest_dir)
        abs_path = os.path.abspath(path)
        if not abs_path.startswith(ingest_root + os.sep) and abs_path != ingest_root:
            return ""
        rel_parent = os.path.relpath(os.path.dirname(abs_path), ingest_root)
        if rel_parent in (".", ""):
            return ""
        # Normalize to forward slashes, then back to OS path when joining
        return rel_parent.replace(os.sep, "/")
    except Exception:
        return ""

def process_file(path: str, source: str = "ingest") -> Job:
    original_name = os.path.basename(path)
    ext = os.path.splitext(original_name)[1].lower()

    job = Job(
        source=source,
        input_path=path,
        original_name=original_name,
        status="failed",
        message="",
        created_at=datetime.utcnow()
    )

    if ext not in SUPPORTED_EXTS:
        job.status = "skipped"
        job.message = f"Unsupported extension: {ext}"
        with get_session() as s:
            s.add(job); s.commit(); s.refresh(job)
        return job

    try:
        text, method = get_text(path)
        text = text or ""

        tpl = _choose_template(text)

        if not tpl:
            job.status = "skipped"
            job.message = f"No matching template (method={method})."
            with get_session() as s:
                s.add(job); s.commit(); s.refresh(job)
            return job

        extracted = extract_fields(tpl, text)
        out_rel, fname = format_path_and_name(tpl, extracted, os.path.splitext(original_name)[0], ext)

        # Preserve original ingest subfolder structure in the library
        rel_subdir = _ingest_relative_subdir(path) if source == "ingest" else ""
        if rel_subdir:
            # Append source structure after the template path, so templates still control top-level routing
            out_rel = os.path.join(out_rel, rel_subdir).replace(os.sep, "/")

        dest_dir = os.path.join(settings.library_dir, out_rel.replace("/", os.sep))
        dest_name = f"{fname}{ext}"
        dest_path = os.path.join(dest_dir, dest_name)

        moved_to = atomic_move(path, dest_path)

        job.status = "ok"
        job.message = f"Processed via template '{tpl.name}' (method={method})."
        job.template_id = tpl.id
        job.doc_folder = tpl.doc_folder
        job.dest_path = moved_to
        job.extracted_company = extracted.company or ""
        job.extracted_invoice_number = extracted.invoice_number or ""
        job.extracted_date = extracted.date.isoformat() if extracted.date else ""

        with get_session() as s:
            s.add(job); s.commit(); s.refresh(job)
        return job

    except Exception as e:
        job.status = "failed"
        job.message = str(e)
        with get_session() as s:
            s.add(job); s.commit(); s.refresh(job)
        return job
