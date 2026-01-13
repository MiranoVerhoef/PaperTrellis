from __future__ import annotations

import os
from typing import List

def scan_library_dirs(library_dir: str, max_depth: int = 5) -> List[str]:
    out: list[str] = []
    library_dir = os.path.abspath(library_dir)
    if not os.path.isdir(library_dir):
        return out

    for root, dirs, _files in os.walk(library_dir):
        rel = os.path.relpath(root, library_dir)
        if rel != ".":
            depth = rel.count(os.sep) + 1
            if depth <= max_depth:
                out.append(rel.replace(os.sep, "/"))
            else:
                dirs[:] = []
                continue

        depth_here = 0 if rel == "." else (rel.count(os.sep) + 1)
        if depth_here >= max_depth:
            dirs[:] = []

    out = sorted(set(out), key=lambda p: (p.count("/"), p.lower()))
    return out
