from __future__ import annotations

import os
import re
import shutil
from typing import Tuple

def safe_filename(name: str, replacement: str = "_") -> str:
    name = (name or "").strip()
    name = name.replace("\x00", "")
    name = re.sub(r'[:*?"<>|]+', replacement, name)
    name = re.sub(r"\s+", " ", name).strip()
    return name or "document"

def ensure_unique_path(path: str) -> str:
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    i = 1
    while True:
        candidate = f"{base}_{i}{ext}"
        if not os.path.exists(candidate):
            return candidate
        i += 1

def atomic_move(src: str, dest: str) -> str:
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    dest = ensure_unique_path(dest)
    shutil.move(src, dest)
    return dest

def file_stat(path: str) -> Tuple[int, float]:
    try:
        st = os.stat(path)
        return int(st.st_size), float(st.st_mtime)
    except Exception:
        return 0, 0.0
