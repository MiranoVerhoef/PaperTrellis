from __future__ import annotations

import os
from datetime import datetime
from typing import Optional, List

from sqlmodel import select

from .db import get_session
from .models import Template, Job, Document
from .ocr import get_text
from .templating import evaluate_template, extract_fields, format_path_and_name
from .settings import settings
from .utils import atomic_move, file_stat, safe_filename

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
    try:
        ingest_root = os.path.abspath(settings.ingest_dir)
        abs_path = os.path.abspath(path)
        if not abs_path.startswith(ingest_root + os.sep) and abs_path != ingest_root:
            return ""
        rel_parent = os.path.relpath(os.path.dirname(abs_path), ingest_root)
        if rel_parent in (".", ""):
            return ""
        return rel_parent.replace(os.sep, "/")
    except Exception:
        return ""

def _normalize_tag(t: str) -> str:
    t = (t or "").strip()
    if not t:
        return ""
    # Keep it simple: lowercase, spaces -> hyphen
    t = t.lower().replace(" ", "-")
    # remove path separators
    t = t.replace("/", "-").replace("\\", "-")
    # keep sane chars
    return "".join(ch for ch in t if ch.isalnum() or ch in "-_").strip("-_")

def _tags_for_template(tpl: Template, company: str) -> List[str]:
    tags: List[str] = []
    dt = _normalize_tag(tpl.doc_type)
    if dt:
        tags.append(dt)
    for t in tpl.tags():
        nt = _normalize_tag(t)
        if nt:
            tags.append(nt)
    if company:
        nt = _normalize_tag(company)
        if nt:
            tags.append(nt)
    # de-dup
    out = []
    seen = set()
    for t in tags:
        if t not in seen:
            out.append(t)
            seen.add(t)
    return out

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
            out_rel = os.path.join(out_rel, rel_subdir).replace(os.sep, "/")

        dest_dir = os.path.join(settings.library_dir, out_rel.replace("/", os.sep))
        dest_name = f"{fname}{ext}"
        dest_path = os.path.join(dest_dir, dest_name)

        moved_to = atomic_move(path, dest_path)
        size, mtime = file_stat(moved_to)

        tags = _tags_for_template(tpl, extracted.company)

        doc = Document(
            location="library",
            abs_path=os.path.abspath(moved_to),
            rel_path=os.path.relpath(os.path.abspath(moved_to), os.path.abspath(settings.library_dir)).replace(os.sep, "/"),
            filename=os.path.basename(moved_to),
            ext=ext,
            status="ok",
            template_id=tpl.id,
            size_bytes=size,
            mtime=mtime,
            extracted_company=extracted.company or "",
            extracted_invoice_number=extracted.invoice_number or "",
            extracted_date=extracted.date.isoformat() if extracted.date else "",
            ocr_text=text[:200000],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        doc.set_tags(tags)

        job.status = "ok"
        job.message = f"Processed via template '{tpl.name}' (method={method})."
        job.template_id = tpl.id
        job.dest_path = moved_to
        job.extracted_company = extracted.company or ""
        job.extracted_invoice_number = extracted.invoice_number or ""
        job.extracted_date = extracted.date.isoformat() if extracted.date else ""

        with get_session() as s:
            s.add(job)
            s.add(doc)
            s.commit()
            s.refresh(job)
        return job

    except Exception as e:
        job.status = "failed"
        job.message = str(e)
        with get_session() as s:
            s.add(job); s.commit(); s.refresh(job)
        return job
