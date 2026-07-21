from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import IntelligenceReport
from .usage import RunUsage


@dataclass(frozen=True, slots=True)
class CachedReport:
    report: IntelligenceReport
    usage: RunUsage
    created_at: datetime


class ReportCache:
    def __init__(self, directory: Path, prompt_version: str) -> None:
        self.directory = directory
        self.prompt_version = prompt_version

    @staticmethod
    def normalize_company(company_name: str) -> str:
        return re.sub(r"\s+", " ", company_name.strip()).casefold()

    def cache_key(
        self,
        company_name: str,
        mode: str,
        research_model: str,
    ) -> str:
        source = "|".join(
            [
                self.prompt_version,
                self.normalize_company(company_name),
                mode,
                research_model,
            ]
        )
        return hashlib.sha256(source.encode("utf-8")).hexdigest()[:24]

    def path_for(
        self,
        company_name: str,
        mode: str,
        research_model: str,
    ) -> Path:
        key = self.cache_key(company_name, mode, research_model)
        return self.directory / f"{key}.json"

    def load(
        self,
        company_name: str,
        mode: str,
        research_model: str,
        max_age_hours: int,
    ) -> CachedReport | None:
        path = self.path_for(company_name, mode, research_model)
        if not path.exists() or max_age_hours <= 0:
            return None

        age_seconds = time.time() - path.stat().st_mtime
        if age_seconds > max_age_hours * 3_600:
            return None

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            created_at = datetime.fromisoformat(payload["created_at"])
            report = IntelligenceReport.model_validate(payload["report"])
            usage = RunUsage.from_dict(payload.get("usage", {}))
            return CachedReport(report, usage, created_at)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def save(
        self,
        company_name: str,
        mode: str,
        research_model: str,
        report: IntelligenceReport,
        usage: RunUsage,
    ) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.path_for(company_name, mode, research_model)
        payload: dict[str, Any] = {
            "created_at": datetime.now(UTC).isoformat(),
            "prompt_version": self.prompt_version,
            "report": report.model_dump(mode="json"),
            "usage": usage.to_dict(),
        }
        temporary_path = path.with_suffix(".tmp")
        temporary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temporary_path.replace(path)
        return path

    def clear(self) -> int:
        if not self.directory.exists():
            return 0
        removed = 0
        for path in self.directory.glob("*.json"):
            path.unlink(missing_ok=True)
            removed += 1
        return removed
