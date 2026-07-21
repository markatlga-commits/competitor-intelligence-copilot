from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .models import IntelligenceReport
from .pdf_report import build_pdf


@dataclass(frozen=True, slots=True)
class ExportPaths:
    json_path: Path
    pdf_path: Path


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug or "company"


def export_report(
    report: IntelligenceReport,
    output_dir: Path,
) -> ExportPaths:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = _timestamp_from_report(report.generated_at)
    stem = f"{slugify(report.target_company)}-{timestamp}"
    json_path = output_dir / f"{stem}.json"
    pdf_path = output_dir / f"{stem}.pdf"

    json_path.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    build_pdf(report, pdf_path)
    return ExportPaths(json_path=json_path, pdf_path=pdf_path)


def _timestamp_from_report(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.strftime("%Y%m%d-%H%M%S")
    except ValueError:
        return datetime.now().strftime("%Y%m%d-%H%M%S")
