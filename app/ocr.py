from __future__ import annotations

import os
from typing import Tuple

from pdfminer.high_level import extract_text as pdf_extract_text
from pdf2image import convert_from_path
from PIL import Image
import pytesseract

from .settings import settings

def get_text(path: str) -> Tuple[str, str]:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        # 1) embedded text
        try:
            text = pdf_extract_text(path) or ""
            if len(text.strip()) >= 30:
                return text, "pdf-text"
        except Exception:
            pass

        # 2) OCR pages
        text_parts = []
        try:
            images = convert_from_path(path, dpi=200, fmt="png", output_folder=settings.tmp_dir)
            for img in images:
                text_parts.append(pytesseract.image_to_string(img, lang=settings.tesseract_lang))
            return "\n".join(text_parts), "pdf-ocr"
        except Exception as e:
            raise RuntimeError(f"OCR failed for PDF: {e}")

    # image OCR
    try:
        with Image.open(path) as img:
            return pytesseract.image_to_string(img, lang=settings.tesseract_lang), "image-ocr"
    except Exception as e:
        raise RuntimeError(f"OCR failed for image: {e}")
