from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Iterable, Tuple

from sqlmodel import select

from .settings import settings
from .db import get_session
from .models import Document
from .processor import SUPPORTED_EXTS
from .utils import file_stat

def _walk_files(root_dir: str) -> Iterable[str]:
    for r, _dirs, files in os.walk(root_dir):
        for fn in files:
            path = os.path.join(r, fn)
            ext = os.path.splitext(fn)[1].lower()
            if ext in SUPPORTED_EXTS:
                yield path

def _upsert_doc(location: str, base_dir: str, path: str) -> None:
    abs_path = os.path.abspath(path)
    rel = os.path.relpath(abs_path, os.path.abspath(base_dir)).replace(os.sep, "/")
    filename = os.path.basename(path)
    ext = os.path.splitext(filename)[1].lower()
    size, mtime = file_stat(path)

    with get_session() as s:
        existing = s.exec(select(Document).where(Document.location == location).where(Document.rel_path == rel)).first()
        if existing:
            if existing.mtime != mtime or existing.size_bytes != size:
                existing.abs_path = abs_path
                existing.filename = filename
                existing.ext = ext
                existing.size_bytes = size
                existing.mtime = mtime
                existing.updated_at = datetime.utcnow()
                s.add(existing)
                s.commit()
            return

        doc = Document(
            location=location,
            abs_path=abs_path,
            rel_path=rel,
            filename=filename,
            ext=ext,
            status="indexed",
            size_bytes=size,
            mtime=mtime,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        s.add(doc)
        s.commit()

def run_index_once() -> None:
    os.makedirs(settings.library_dir, exist_ok=True)
    os.makedirs(settings.failed_dir, exist_ok=True)

    for path in _walk_files(settings.library_dir):
        _upsert_doc("library", settings.library_dir, path)

    for path in _walk_files(settings.failed_dir):
        _upsert_doc("failed", settings.failed_dir, path)

def start_indexer_thread() -> None:
    interval = max(10, int(settings.scan_interval_seconds or 15))

    def _loop():
        while True:
            try:
                run_index_once()
            except Exception:
                pass
            time.sleep(interval)

    import threading
    t = threading.Thread(target=_loop, daemon=True, name="papertrellis-indexer")
    t.start()
