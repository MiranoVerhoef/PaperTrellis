from __future__ import annotations

import os
import re
import shutil

def safe_filename(name: str, replacement: str = "_") -> str:
    name = name.strip()
    # Remove path separators and dangerous characters
    name = re.sub(r"[\\/\0]+", replacement, name)
    name = re.sub(r'[:*?"<>|]+', replacement, name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:200] if len(name) > 200 else name

def ensure_unique_path(path: str) -> str:
    if not os.path.exists(path):
        return path
    root, ext = os.path.splitext(path)
    i = 1
    while True:
        candidate = f"{root}_{i}{ext}"
        if not os.path.exists(candidate):
            return candidate
        i += 1

def atomic_move(src: str, dst: str) -> str:
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    dst = ensure_unique_path(dst)
    shutil.move(src, dst)
    return dst
