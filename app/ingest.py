from __future__ import annotations

import os
import time
from typing import Set

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileMovedEvent

from .settings import settings
from .processor import process_file
from .utils import atomic_move, safe_filename, file_stat
from .db import get_session
from .models import Document

def _ingest_relative_subdir(path: str) -> str:
    try:
        ingest_root = os.path.abspath(settings.ingest_dir)
        abs_path = os.path.abspath(path)
        if not abs_path.startswith(ingest_root + os.sep) and abs_path != ingest_root:
            return ""
        rel_parent = os.path.relpath(os.path.dirname(abs_path), ingest_root)
        if rel_parent in (".", ""):
            return ""
        return rel_parent
    except Exception:
        return ""

class _Handler(FileSystemEventHandler):
    def __init__(self) -> None:
        super().__init__()
        self._seen: Set[str] = set()

    def _maybe_process(self, path: str) -> None:
        if not os.path.isfile(path):
            return

        norm = os.path.abspath(path)
        if norm in self._seen:
            return
        self._seen.add(norm)

        # wait for write to settle
        for _ in range(24):
            try:
                size1 = os.path.getsize(path)
                time.sleep(0.25)
                size2 = os.path.getsize(path)
                if size1 == size2 and size2 > 0:
                    break
            except FileNotFoundError:
                return

        job = process_file(path, source="ingest")

        if job.status != "ok":
            try:
                if os.path.exists(path):
                    rel_subdir = _ingest_relative_subdir(path)
                    failed_dir = os.path.abspath(settings.failed_dir)
                    dest_dir = os.path.join(failed_dir, rel_subdir) if rel_subdir else failed_dir
                    base_name = safe_filename(os.path.basename(path))
                    dest_path = os.path.join(dest_dir, base_name)
                    moved_to = atomic_move(path, dest_path)

                    size, mtime = file_stat(moved_to)
                    doc = Document(
                        location="failed",
                        abs_path=os.path.abspath(moved_to),
                        rel_path=os.path.relpath(os.path.abspath(moved_to), os.path.abspath(settings.failed_dir)).replace(os.sep, "/"),
                        filename=os.path.basename(moved_to),
                        ext=os.path.splitext(moved_to)[1].lower(),
                        status=job.status,
                        template_id=job.template_id,
                        extracted_company=job.extracted_company or "",
                        extracted_invoice_number=job.extracted_invoice_number or "",
                        extracted_date=job.extracted_date or "",
                        size_bytes=size,
                        mtime=mtime,
                    )
                    # tag it for easy filtering
                    doc.set_tags(["failed"] if job.status == "failed" else ["unmatched"])
                    with get_session() as s:
                        s.add(doc)
                        s.commit()
            except Exception:
                pass

    def on_created(self, event):
        if isinstance(event, FileCreatedEvent):
            self._maybe_process(event.src_path)

    def on_moved(self, event):
        if isinstance(event, FileMovedEvent):
            self._maybe_process(event.dest_path)

class IngestService:
    def __init__(self) -> None:
        self.observer: Observer | None = None

    def start(self) -> None:
        if not settings.scan_enabled:
            return
        os.makedirs(settings.ingest_dir, exist_ok=True)
        os.makedirs(settings.library_dir, exist_ok=True)
        os.makedirs(settings.failed_dir, exist_ok=True)
        os.makedirs(settings.tmp_dir, exist_ok=True)

        handler = _Handler()
        observer = Observer()
        observer.schedule(handler, settings.ingest_dir, recursive=True)
        observer.start()
        self.observer = observer

    def stop(self) -> None:
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=5)

ingest_service = IngestService()
