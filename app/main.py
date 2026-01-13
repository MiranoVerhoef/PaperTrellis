from __future__ import annotations

import os
import json
from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from sqlmodel import select

from .version import __version__
from .settings import settings
from .db import init_db, get_session
from .models import Template, Document, Job
from .auth import auth_config_ok, SESSION_KEY, try_login, is_logged_in
from .seed import seed_defaults
from .library_scan import scan_library_dirs
from .indexer import start_indexer_thread
from .ingest import ingest_service
from .processor import process_file
from .ocr import get_text
from .templating import evaluate_template, extract_fields

from jinja2 import Environment, FileSystemLoader, select_autoescape

BASE_DIR = os.path.dirname(__file__)
TEMPLATES_DIR = os.path.join(BASE_DIR, "ui", "templates")

jinja = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html", "xml"])
)

app = FastAPI(title="PaperTrellis")

# Sessions for login (single-user)
if settings.auth_enabled:
    app.add_middleware(SessionMiddleware, secret_key=settings.session_secret or "CHANGEME")

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "ui", "static")), name="static")

def render(request: Request, template: str, **ctx) -> HTMLResponse:
    ctx.setdefault("request", request)
    ctx.setdefault("app_version", __version__)
    ctx.setdefault("logged_in", is_logged_in(request))
    ctx.setdefault("auth_enabled", settings.auth_enabled)
    ctx.setdefault("now", datetime.utcnow())
    html = jinja.get_template(template).render(**ctx)
    return HTMLResponse(html)

def require_login_or_redirect(request: Request) -> Optional[Response]:
    if not settings.auth_enabled:
        return None
    if not is_logged_in(request):
        return RedirectResponse("/login", status_code=303)
    return None

def _safe_resolve_doc_path(doc: Document) -> str:
    base_dir = settings.library_dir if doc.location == "library" else settings.failed_dir
    abs_base = os.path.abspath(base_dir)
    abs_path = os.path.abspath(doc.abs_path)
    if not abs_path.startswith(abs_base + os.sep) and abs_path != abs_base:
        raise ValueError("Invalid path")
    return abs_path

@app.on_event("startup")
def _startup():
    os.makedirs(settings.config_dir, exist_ok=True)
    os.makedirs(settings.library_dir, exist_ok=True)
    os.makedirs(settings.ingest_dir, exist_ok=True)
    os.makedirs(settings.failed_dir, exist_ok=True)
    os.makedirs(settings.tmp_dir, exist_ok=True)

    init_db()
    seed_defaults()
    start_indexer_thread()
    ingest_service.start()

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    r = require_login_or_redirect(request)
    if r:
        return r
    return RedirectResponse("/documents", status_code=303)

# --- Auth ---
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if not settings.auth_enabled:
        return RedirectResponse("/documents", status_code=303)

    return render(
        request,
        "login.html",
        config_ok=auth_config_ok(),
        error=""
    )

@app.post("/login")
def login_post(request: Request, password: str = Form(default="")):
    if not settings.auth_enabled:
        return RedirectResponse("/documents", status_code=303)

    if not auth_config_ok():
        return render(request, "login.html", config_ok=False, error="Server not configured for login.")

    if try_login(password):
        request.session[SESSION_KEY] = True
        return RedirectResponse("/documents", status_code=303)

    return render(request, "login.html", config_ok=True, error="Invalid password.")

@app.get("/logout")
def logout(request: Request):
    if settings.auth_enabled:
        request.session.pop(SESSION_KEY, None)
    return RedirectResponse("/login", status_code=303)

# --- Documents ---
@app.get("/documents", response_class=HTMLResponse)
def documents(
    request: Request,
    q: str = "",
    tag: str = "",
    status: str = "",
    location: str = "",
    page: int = 1
):
    r = require_login_or_redirect(request)
    if r:
        return r

    per_page = 50
    page = max(1, int(page))
    offset = (page - 1) * per_page

    with get_session() as s:
        stmt = select(Document).order_by(Document.updated_at.desc())

        if location in ("library", "failed"):
            stmt = stmt.where(Document.location == location)

        if status:
            stmt = stmt.where(Document.status == status)

        q = (q or "").strip()
        if q:
            # lightweight search
            like = f"%{q}%"
            stmt = stmt.where(
                (Document.filename.like(like)) | (Document.rel_path.like(like)) | (Document.ocr_text.like(like))
            )

        tag = (tag or "").strip().lower()
        if tag:
            stmt = stmt.where(Document.tags_json.like(f'%"{tag}"%'))

        docs = s.exec(stmt.offset(offset).limit(per_page + 1)).all()
        has_more = len(docs) > per_page
        docs = docs[:per_page]

    return render(
        request,
        "documents.html",
        docs=docs,
        q=q,
        tag=tag,
        status=status,
        location=location,
        page=page,
        has_more=has_more
    )

@app.get("/documents/{doc_id}", response_class=HTMLResponse)
def document_detail(request: Request, doc_id: int):
    r = require_login_or_redirect(request)
    if r:
        return r

    with get_session() as s:
        doc = s.get(Document, doc_id)
        if not doc:
            return render(request, "error.html", title="Not found", message="Document not found.")

        # load template name
        tpl = s.get(Template, doc.template_id) if doc.template_id else None

    return render(request, "document_detail.html", doc=doc, template=tpl)

@app.get("/documents/{doc_id}/file")
def document_file(request: Request, doc_id: int):
    r = require_login_or_redirect(request)
    if r:
        return r

    with get_session() as s:
        doc = s.get(Document, doc_id)
        if not doc:
            return Response(status_code=404)

    path = _safe_resolve_doc_path(doc)
    return FileResponse(path, filename=doc.filename)

@app.post("/documents/{doc_id}/tags")
def update_doc_tags(request: Request, doc_id: int, tags: str = Form(default="")):
    r = require_login_or_redirect(request)
    if r:
        return r

    tags_list = [t.strip().lower() for t in (tags or "").split(",") if t.strip()]
    with get_session() as s:
        doc = s.get(Document, doc_id)
        if not doc:
            return RedirectResponse("/documents", status_code=303)
        doc.set_tags(tags_list)
        doc.updated_at = datetime.utcnow()
        s.add(doc)
        s.commit()
    return RedirectResponse(f"/documents/{doc_id}", status_code=303)

@app.post("/documents/{doc_id}/analyze")
def analyze_doc(request: Request, doc_id: int):
    r = require_login_or_redirect(request)
    if r:
        return r

    with get_session() as s:
        doc = s.get(Document, doc_id)
        if not doc:
            return RedirectResponse("/documents", status_code=303)

        path = _safe_resolve_doc_path(doc)

        try:
            text, _method = get_text(path)
        except Exception as e:
            return render(request, "error.html", title="Analyze failed", message=str(e))

        doc.ocr_text = (text or "")[:200000]

        # try matching templates
        templates = s.exec(select(Template).where(Template.enabled == True)).all()  # noqa: E712
        best = None
        best_score = -1
        for tpl in templates:
            ok, score = evaluate_template(tpl, doc.ocr_text)
            if ok and score >= best_score:
                best = tpl
                best_score = score

        if best:
            ex = extract_fields(best, doc.ocr_text)
            doc.template_id = best.id
            doc.extracted_company = ex.company or ""
            doc.extracted_invoice_number = ex.invoice_number or ""
            doc.extracted_date = ex.date.isoformat() if ex.date else ""
            # keep existing tags, but add template tags
            tags = set(doc.tags())
            tags.add((best.doc_type or "document").lower().replace(" ", "-"))
            for t in best.tags():
                tags.add(t.lower().replace(" ", "-"))
            if ex.company:
                tags.add(ex.company.lower().replace(" ", "-"))
            doc.set_tags(sorted(tags))

        doc.updated_at = datetime.utcnow()
        s.add(doc)
        s.commit()

    return RedirectResponse(f"/documents/{doc_id}", status_code=303)

# --- Upload ---
@app.post("/upload")
async def upload(request: Request, file: UploadFile = File(...)):
    r = require_login_or_redirect(request)
    if r:
        return r

    if not file.filename:
        return RedirectResponse("/documents", status_code=303)

    os.makedirs(settings.tmp_dir, exist_ok=True)
    tmp_path = os.path.join(settings.tmp_dir, f"upload_{datetime.utcnow().timestamp()}_{os.path.basename(file.filename)}")

    with open(tmp_path, "wb") as f:
        f.write(await file.read())

    # process as upload (goes to library if matches template)
    process_file(tmp_path, source="upload")
    return RedirectResponse("/documents", status_code=303)

# --- Tags ---
@app.get("/tags", response_class=HTMLResponse)
def tags_page(request: Request):
    r = require_login_or_redirect(request)
    if r:
        return r

    counts = {}
    with get_session() as s:
        docs = s.exec(select(Document.tags_json)).all()
        for (tags_json,) in docs:
            try:
                arr = json.loads(tags_json or "[]")
                for t in arr:
                    t = str(t).strip().lower()
                    if not t:
                        continue
                    counts[t] = counts.get(t, 0) + 1
            except Exception:
                continue

    tags = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return render(request, "tags.html", tags=tags)

# --- Templates ---
@app.get("/templates", response_class=HTMLResponse)
def templates_page(request: Request):
    r = require_login_or_redirect(request)
    if r:
        return r

    with get_session() as s:
        templates = s.exec(select(Template).order_by(Template.name.asc())).all()

    library_dirs = scan_library_dirs(settings.library_dir, max_depth=6)
    return render(request, "templates.html", templates=templates, library_dirs=library_dirs)

@app.get("/templates/new", response_class=HTMLResponse)
def template_new(request: Request):
    r = require_login_or_redirect(request)
    if r:
        return r
    library_dirs = scan_library_dirs(settings.library_dir, max_depth=6)
    return render(request, "template_edit.html", tpl=None, library_dirs=library_dirs, error="")

@app.get("/templates/{tpl_id}", response_class=HTMLResponse)
def template_edit(request: Request, tpl_id: int):
    r = require_login_or_redirect(request)
    if r:
        return r

    with get_session() as s:
        tpl = s.get(Template, tpl_id)
        if not tpl:
            return RedirectResponse("/templates", status_code=303)

    library_dirs = scan_library_dirs(settings.library_dir, max_depth=6)
    return render(request, "template_edit.html", tpl=tpl, library_dirs=library_dirs, error="")

@app.post("/templates/save")
def template_save(
    request: Request,
    tpl_id: str = Form(default=""),
    name: str = Form(default=""),
    enabled: str = Form(default="on"),
    doc_type: str = Form(default="Document"),
    doc_folder: str = Form(default="Inbox"),
    tags: str = Form(default=""),
    match_mode: str = Form(default="all"),
    match_patterns: str = Form(default=""),
    company_regex: str = Form(default=""),
    invoice_number_regex: str = Form(default=""),
    date_regex: str = Form(default=""),
    output_path_template: str = Form(default="{doc_folder}/{company}/{date:%Y}"),
    filename_template: str = Form(default="{company}_{invoice_number}_{date:%Y-%m-%d}"),
):
    r = require_login_or_redirect(request)
    if r:
        return r

    name = name.strip()
    if not name:
        library_dirs = scan_library_dirs(settings.library_dir, max_depth=6)
        return render(request, "template_edit.html", tpl=None, library_dirs=library_dirs, error="Name is required.")

    tags_list = [t.strip() for t in (tags or "").split(",") if t.strip()]
    patterns_list = [p.strip() for p in (match_patterns or "").splitlines() if p.strip()]

    with get_session() as s:
        tpl: Optional[Template] = None
        if tpl_id.strip().isdigit():
            tpl = s.get(Template, int(tpl_id))
        if not tpl:
            tpl = Template(name=name)

        tpl.name = name
        tpl.enabled = (enabled == "on")
        tpl.doc_type = doc_type.strip() or "Document"
        tpl.doc_folder = doc_folder.strip() or "Inbox"
        tpl.set_tags(tags_list)
        tpl.match_mode = match_mode if match_mode in ("all", "any") else "all"
        tpl.set_match_patterns(patterns_list)
        tpl.company_regex = company_regex.strip()
        tpl.invoice_number_regex = invoice_number_regex.strip()
        tpl.date_regex = date_regex.strip()
        tpl.output_path_template = output_path_template.strip() or "{doc_folder}"
        tpl.filename_template = filename_template.strip() or "{original_name}"

        s.add(tpl)
        s.commit()
        s.refresh(tpl)

    return RedirectResponse("/templates", status_code=303)

@app.post("/templates/{tpl_id}/delete")
def template_delete(request: Request, tpl_id: int):
    r = require_login_or_redirect(request)
    if r:
        return r

    with get_session() as s:
        tpl = s.get(Template, tpl_id)
        if tpl:
            s.delete(tpl)
            s.commit()
    return RedirectResponse("/templates", status_code=303)

# --- Ingest / Failed ---
@app.get("/ingest", response_class=HTMLResponse)
def ingest_page(request: Request):
    r = require_login_or_redirect(request)
    if r:
        return r
    return render(
        request,
        "ingest.html",
        ingest_dir=settings.ingest_dir,
        library_dir=settings.library_dir,
        failed_dir=settings.failed_dir,
        scan_enabled=settings.scan_enabled,
        scan_interval=settings.scan_interval_seconds,
        tesseract_lang=settings.tesseract_lang
    )

@app.get("/failed", response_class=HTMLResponse)
def failed_page(request: Request, q: str = "", page: int = 1):
    return documents(request, q=q, tag="", status="", location="failed", page=page)


@app.on_event("shutdown")
def _shutdown():
    try:
        ingest_service.stop()
    except Exception:
        pass
