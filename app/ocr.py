from __future__ import annotations

import os
from typing import Tuple
from PIL import Image
import pytesseract
from pdfminer.high_level import extract_text
from pdf2image import convert_from_path

from .settings import settings

SUPPORTED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
SUPPORTED_PDF_EXTS = {".pdf"}

def extract_text_from_pdf(path: str) -> str:
    try:
        txt = extract_text(path) or ""
    except Exception:
        txt = ""
    return txt

def ocr_pdf(path: str) -> str:
    # Render pages to images, then OCR each page
    images = convert_from_path(path, dpi=250, fmt="png", output_folder=settings.tmp_dir)
    chunks: list[str] = []
    for img in images:
        chunks.append(pytesseract.image_to_string(img, lang=settings.tesseract_lang))
    return "\n".join(chunks)

def ocr_image(path: str) -> str:
    img = Image.open(path)
    return pytesseract.image_to_string(img, lang=settings.tesseract_lang)

def get_text(path: str) -> Tuple[str, str]:
    """Return (text, method) where method in {'text','ocr'}"""
    ext = os.path.splitext(path)[1].lower()

    if ext in SUPPORTED_PDF_EXTS:
        txt = extract_text_from_pdf(path)
        if len((txt or "").strip()) >= settings.pdf_text_min_chars:
            return txt, "text"
        return ocr_pdf(path), "ocr"

    if ext in SUPPORTED_IMAGE_EXTS:
        return ocr_image(path), "ocr"

    # Fallback: try pdfminer anyway; otherwise no text
    txt = ""
    try:
        txt = extract_text(path) or ""
    except Exception:
        pass
    return txt, "text" if txt.strip() else "none"
