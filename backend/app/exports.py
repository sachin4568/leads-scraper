from __future__ import annotations

import csv
import io

from backend.app.models import Lead


def sanitize_cell(value: object | None) -> str:
    text = "" if value is None else str(value)
    return f"'{text}" if text.startswith(("=", "+", "-", "@")) else text


def leads_to_csv(leads: list[Lead]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Business name", "Website", "Email", "Phone", "Notes"])
    for lead in leads:
        writer.writerow(
            [
                sanitize_cell(value)
                for value in (lead.business_name, lead.website, lead.email, lead.phone, lead.notes)
            ]
        )
    return output.getvalue()


def leads_to_xlsx(leads: list[Lead]) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Leads"
    ws.append(["Business name", "Website", "Email", "Phone", "Notes"])
    for lead in leads:
        ws.append(
            [
                sanitize_cell(value)
                for value in (lead.business_name, lead.website, lead.email, lead.phone, lead.notes)
            ]
        )
    stream = io.BytesIO()
    wb.save(stream)
    return stream.getvalue()
