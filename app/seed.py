from __future__ import annotations

from sqlmodel import select
from .db import get_session
from .models import Template

def seed_defaults() -> None:
    with get_session() as s:
        existing = s.exec(select(Template)).first()
        if existing:
            return

        tpl = Template(
            name="Invoice (generic)",
            enabled=True,
            doc_type="Invoice",
            doc_folder="Invoices",
            match_mode="any",
            # These are intentionally broad. You can tighten them in the UI.
        )
        tpl.set_match_patterns([
            r"\binvoice\b",
            r"\bfactuur\b",
            r"\bvat\b",
        ])
        tpl.company_regex = r"(?i)from\s*:\s*(.+)"
        tpl.invoice_number_regex = r"(?i)(?:invoice\s*(?:no|number)|factuurnummer)\s*[:#]?\s*([A-Z0-9\-\/]+)"
        tpl.date_regex = r"(?i)(?:invoice\s*date|factuurdatum|date)\s*[:]?\s*([0-9]{1,2}[-/.][0-9]{1,2}[-/.][0-9]{2,4})"
        tpl.output_path_template = "{doc_folder}/{company}/{date:%Y}"
        tpl.filename_template = "{company}_{invoice_number}_{date:%Y-%m-%d}"
        tpl.set_tags(["invoice"])

        s.add(tpl)
        s.commit()
