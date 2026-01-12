from __future__ import annotations

import os
import time
from typing import Set

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileMovedEvent

from .settings import settings
from .processor import process_file
from .utils import atomic_move, safe_filename

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

        # Avoid double processing
        norm = os.path.abspath(path)
        if norm in self._seen:
            return
        self._seen.add(norm)

        # Wait a bit for file to finish writing (best-effort)
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

        # If ingest processing did not succeed, move the file to the failed folder (non-destructive to library)
        if job.status != "ok":
            try:
                if os.path.exists(path):
                    rel_subdir = _ingest_relative_subdir(path)
                    failed_dir = os.path.abspath(settings.failed_dir)
                    dest_dir = os.path.join(failed_dir, rel_subdir) if rel_subdir else failed_dir
                    base_name = safe_filename(os.path.basename(path))
                    dest_path = os.path.join(dest_dir, base_name)
                    atomic_move(path, dest_path)
            except Exception:
                # If even the fail-move fails, leave the file in place.
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
        os.makedirs(settings.failed_dir, exist_ok=True)

        handler = _Handler()
        observer = Observer()
        # recursive=True so we preserve original ingest subfolder structure
        observer.schedule(handler, settings.ingest_dir, recursive=True)
        observer.start()
        self.observer = observer

    def stop(self) -> None:
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=5)

ingest_service = IngestService()
