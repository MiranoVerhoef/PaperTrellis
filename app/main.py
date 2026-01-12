from __future__ import annotations

import os
import uuid
from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import select

from .settings import settings
from .db import init_db, get_session
from .models import Template, Job
from .seed import seed_defaults
from .processor import process_file
from .templating import evaluate_template, extract_fields, format_path_and_name
from .ingest import ingest_service
from .library_scan import scan_library_dirs
from .version import __version__

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "ui", "templates")
env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(["html", "xml"])
)

app = FastAPI(title="PaperTrellis")

static_dir = os.path.join(os.path.dirname(__file__), "ui", "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.on_event("startup")
def on_startup() -> None:
    os.makedirs(settings.tmp_dir, exist_ok=True)
    os.makedirs(settings.library_dir, exist_ok=True)
    os.makedirs(settings.ingest_dir, exist_ok=True)
    os.makedirs(settings.config_dir, exist_ok=True)

    init_db()
    seed_defaults()
    ingest_service.start()

@app.on_event("shutdown")
def on_shutdown() -> None:
    ingest_service.stop()

def render(template_name: str, **ctx):
    ctx.setdefault("app_version", __version__)
    tpl = env.get_template(template_name)
    return HTMLResponse(tpl.render(**ctx))

@app.get("/", response_class=HTMLResponse)
def index():
    with get_session() as s:
        jobs = s.exec(select(Job).order_by(Job.created_at.desc()).limit(20)).all()
    return render(
        "index.html",
        title="Dashboard",
        jobs=jobs,
        ingest_dir=settings.ingest_dir,
        library_dir=settings.library_dir,
        scan_enabled=settings.scan_enabled,
        tesseract_lang=settings.tesseract_lang,
        failed_dir=settings.failed_dir
    )

@app.get("/upload", response_class=HTMLResponse)
def upload_page():
    return render("upload.html", title="Manual Upload", result=None)

@app.post("/upload", response_class=HTMLResponse)
async def upload_file(file: UploadFile = File(...)):
    os.makedirs(settings.tmp_dir, exist_ok=True)
    tmp_name = f"upload_{uuid.uuid4().hex}_{os.path.basename(file.filename)}"
    tmp_path = os.path.join(settings.tmp_dir, tmp_name)

    with open(tmp_path, "wb") as f:
        f.write(await file.read())

    job = process_file(tmp_path, source="upload")
    return render("upload.html", title="Manual Upload", result=job)

@app.get("/settings", response_class=HTMLResponse)
def settings_page():
    return render(
        "settings.html",
        title="Ingest Settings",
        ingest_dir=settings.ingest_dir,
        library_dir=settings.library_dir,
        scan_enabled=settings.scan_enabled,
        scan_interval_seconds=settings.scan_interval_seconds,
        tesseract_lang=settings.tesseract_lang,
        failed_dir=settings.failed_dir
    )

@app.post("/settings")
def settings_save(
    ingest_dir: str = Form("/data/ingest"),
    library_dir: str = Form("/data/library"),
    scan_enabled: str = Form("true"),
    scan_interval_seconds: int = Form(15),
    tesseract_lang: str = Form("eng")
):
    # Update runtime settings (note: watcher uses settings at startup)
    settings.ingest_dir = ingest_dir.strip() or settings.ingest_dir
    settings.library_dir = library_dir.strip() or settings.library_dir
    settings.scan_enabled = (scan_enabled.lower() == "true")
    settings.scan_interval_seconds = int(scan_interval_seconds)
    settings.tesseract_lang = tesseract_lang.strip() or settings.tesseract_lang

    # Ensure directories exist
    os.makedirs(settings.ingest_dir, exist_ok=True)
    os.makedirs(settings.library_dir, exist_ok=True)

    return RedirectResponse(url="/settings", status_code=303)

@app.get("/templates", response_class=HTMLResponse)
def templates_list():
    with get_session() as s:
        templates = s.exec(select(Template).order_by(Template.id.asc())).all()
    return render("templates.html", title="Templates", templates=templates)

def _template_from_form(
    name: str,
    enabled: str,
    doc_folder: str,
    match_mode: str,
    match_patterns: str,
    company_regex: str,
    invoice_number_regex: str,
    date_regex: str,
    output_path_template: str,
    filename_template: str
) -> dict:
    patterns = [p.strip() for p in (match_patterns or "").splitlines() if p.strip()]
    return dict(
        name=name.strip(),
        enabled=(enabled.lower() == "true"),
        doc_folder=doc_folder.strip() or "Invoices",
        match_mode=(match_mode.strip() or "all"),
        match_patterns=patterns,
        company_regex=company_regex.strip(),
        invoice_number_regex=invoice_number_regex.strip(),
        date_regex=date_regex.strip(),
        output_path_template=output_path_template.strip(),
        filename_template=filename_template.strip(),
    )

@app.get("/templates/new", response_class=HTMLResponse)
def template_new():
    t = Template(
        name="",
        enabled=True,
        doc_folder="Invoices",
        match_mode="any",
        match_patterns=[r"\binvoice\b"],
        company_regex=r"(?im)^(?:seller|vendor|company|from)\s*[:\-]\s*(.+)$",
        invoice_number_regex=r"(?im)invoice\s*(?:no|number|nr)\.?\s*[:\-]?\s*([A-Z0-9\-\/]+)",
        date_regex=r"(?im)date\s*[:\-]?\s*([0-9]{4}[-/][0-9]{1,2}[-/][0-9]{1,2}|[0-9]{1,2}[-/][0-9]{1,2}[-/][0-9]{2,4})",
        output_path_template="{doc_folder}/{company}/{date:%Y}",
        filename_template="{company}_{invoice_number}_{date:%Y-%m-%d}",
    )
    return render("template_edit.html", title="New Template", t=t, is_new=True, action="/templates/new", library_dirs=scan_library_dirs(settings.library_dir))

@app.post("/templates/new")
def template_create(
    name: str = Form(...),
    enabled: str = Form("true"),
    doc_folder: str = Form("Invoices"),
    match_mode: str = Form("any"),
    match_patterns: str = Form(""),
    company_regex: str = Form(""),
    invoice_number_regex: str = Form(""),
    date_regex: str = Form(""),
    output_path_template: str = Form("{doc_folder}/{company}"),
    filename_template: str = Form("{company}_{invoice_number}_{date:%Y-%m-%d}")
):
    data = _template_from_form(
        name, enabled, doc_folder, match_mode, match_patterns,
        company_regex, invoice_number_regex, date_regex,
        output_path_template, filename_template
    )
    with get_session() as s:
        t = Template(**data)
        s.add(t); s.commit(); s.refresh(t)
    return RedirectResponse(url="/templates", status_code=303)

@app.get("/templates/{template_id}", response_class=HTMLResponse)
def template_edit(template_id: int):
    with get_session() as s:
        t = s.get(Template, template_id)
        if not t:
            return RedirectResponse(url="/templates", status_code=303)
    return render("template_edit.html", title="Edit Template", t=t, is_new=False, action=f"/templates/{template_id}", library_dirs=scan_library_dirs(settings.library_dir))

@app.post("/templates/{template_id}")
def template_update(
    template_id: int,
    name: str = Form(...),
    enabled: str = Form("true"),
    doc_folder: str = Form("Invoices"),
    match_mode: str = Form("any"),
    match_patterns: str = Form(""),
    company_regex: str = Form(""),
    invoice_number_regex: str = Form(""),
    date_regex: str = Form(""),
    output_path_template: str = Form("{doc_folder}/{company}"),
    filename_template: str = Form("{company}_{invoice_number}_{date:%Y-%m-%d}")
):
    data = _template_from_form(
        name, enabled, doc_folder, match_mode, match_patterns,
        company_regex, invoice_number_regex, date_regex,
        output_path_template, filename_template
    )
    with get_session() as s:
        t = s.get(Template, template_id)
        if not t:
            return RedirectResponse(url="/templates", status_code=303)
        for k, v in data.items():
            setattr(t, k, v)
        s.add(t); s.commit()
    return RedirectResponse(url="/templates", status_code=303)

@app.post("/templates/{template_id}/delete")
def template_delete(template_id: int):
    with get_session() as s:
        t = s.get(Template, template_id)
        if t:
            s.delete(t); s.commit()
    return RedirectResponse(url="/templates", status_code=303)

@app.get("/templates/test", response_class=HTMLResponse)
def templates_test_page(template_id: str | None = None):
    with get_session() as s:
        templates = s.exec(select(Template).order_by(Template.id.asc())).all()
    return render("templates_test.html", title="Test Templates", templates=templates, result=None, text="", template_id=template_id)

@app.post("/templates/test", response_class=HTMLResponse)
def templates_test_run(text: str = Form(""), template_id: str = Form("")):
    with get_session() as s:
        templates = s.exec(select(Template).where(Template.enabled == True)).all()  # noqa: E712

    chosen = None
    if template_id:
        try:
            tid = int(template_id)
            with get_session() as s:
                chosen = s.get(Template, tid)
        except Exception:
            chosen = None
    else:
        best_score = -1
        for tpl in templates:
            ok, score = evaluate_template(tpl, text)
            if ok and score >= best_score:
                best_score = score
                chosen = tpl

    with get_session() as s:
        all_templates = s.exec(select(Template).order_by(Template.id.asc())).all()

    if not chosen:
        return render(
            "templates_test.html",
            title="Test Templates",
            templates=all_templates,
            text=text,
            template_id=template_id,
            result=None
        )

    extracted = extract_fields(chosen, text)
    out_rel, fname = format_path_and_name(chosen, extracted, "sample", ".pdf")

    result = {
        "template_name": f"{chosen.id} - {chosen.name}",
        "company": extracted.company or "",
        "invoice_number": extracted.invoice_number or "",
        "date": extracted.date.isoformat() if extracted.date else "",
        "out_rel": out_rel,
        "filename": fname + ".pdf"
    }
    return render(
        "templates_test.html",
        title="Test Templates",
        templates=all_templates,
        text=text,
        template_id=template_id,
        result=result
    )
