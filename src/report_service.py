from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from .anthropic_client import ClaudeResearchClient
from .cache import ReportCache
from .config import ResearchProfile, Settings, get_profile
from .models import IntelligenceReport
from .usage import RunUsage


@dataclass(frozen=True, slots=True)
class ReportResult:
    report: IntelligenceReport
    usage: RunUsage
    cache_hit: bool
    cached_at: datetime | None
    profile: ResearchProfile


def generate_report(
    company_name: str,
    mode: str,
    settings: Settings,
    force_refresh: bool = False,
    progress: Callable[[str], None] | None = None,
) -> ReportResult:
    normalized_company = " ".join(company_name.split()).strip()
    if not normalized_company:
        raise ValueError("Enter a company name.")

    profile = get_profile(mode)
    cache = ReportCache(settings.cache_dir, settings.prompt_version)

    if not force_refresh:
        cached = cache.load(
            company_name=normalized_company,
            mode=profile.key,
            research_model=settings.research_model,
            max_age_hours=profile.cache_hours,
        )
        if cached is not None:
            if progress:
                progress("Loaded a recent cached report")
            return ReportResult(
                report=cached.report,
                usage=cached.usage,
                cache_hit=True,
                cached_at=cached.created_at,
                profile=profile,
            )

    client = ClaudeResearchClient(settings, profile)
    run_result = client.run(normalized_company, progress=progress)
    cache.save(
        company_name=normalized_company,
        mode=profile.key,
        research_model=settings.research_model,
        report=run_result.report,
        usage=run_result.usage,
    )
    return ReportResult(
        report=run_result.report,
        usage=run_result.usage,
        cache_hit=False,
        cached_at=None,
        profile=profile,
    )
