from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class ResearchProfile:
    key: str
    label: str
    description: str
    max_searches: int
    research_max_tokens: int
    effort: str
    thinking: str
    cache_hours: int
    timeout_seconds: int


PROFILES: dict[str, ResearchProfile] = {
    "quick": ResearchProfile(
        key="quick",
        label="Quick",
        description="A focused executive overview.",
        max_searches=2,
        research_max_tokens=6_500,
        effort="low",
        thinking="disabled",
        cache_hours=24,
        timeout_seconds=120,
    ),
    "balanced": ResearchProfile(
        key="balanced",
        label="Balanced",
        description="Additional evidence and strategic detail.",
        max_searches=3,
        research_max_tokens=8_500,
        effort="medium",
        thinking="disabled",
        cache_hours=12,
        timeout_seconds=180,
    ),
    "deep": ResearchProfile(
        key="deep",
        label="Deep",
        description="A broader review for complex strategic assessments.",
        max_searches=5,
        research_max_tokens=11_000,
        effort="high",
        thinking="disabled",
        cache_hours=6,
        timeout_seconds=240,
    ),
}


@dataclass(frozen=True, slots=True)
class Settings:
    anthropic_api_key: str
    research_model: str
    web_search_tool: str
    default_mode: str
    cache_dir: Path
    output_dir: Path
    prompt_version: str
    max_continuations: int

    @property
    def api_key_configured(self) -> bool:
        return bool(self.anthropic_api_key.strip())


def load_settings() -> Settings:
    load_dotenv()
    default_mode = os.getenv("DEFAULT_RESEARCH_MODE", "quick").lower()
    if default_mode not in PROFILES:
        default_mode = "quick"

    return Settings(
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", "").strip(),
        research_model=os.getenv("RESEARCH_MODEL", "claude-sonnet-5").strip(),
        web_search_tool=os.getenv(
            "WEB_SEARCH_TOOL", "web_search_20260318"
        ).strip(),
        default_mode=default_mode,
        cache_dir=Path(os.getenv("CACHE_DIR", ".cache/reports")),
        output_dir=Path(os.getenv("OUTPUT_DIR", "outputs")),
        prompt_version=os.getenv(
            "PROMPT_VERSION",
            "2026-07-21-three-competitors-v8-complete-sentences",
        ).strip(),
        max_continuations=max(1, int(os.getenv("MAX_CONTINUATIONS", "3"))),
    )


def get_profile(mode: str | None) -> ResearchProfile:
    selected = (mode or "quick").lower()
    profile = PROFILES.get(selected, PROFILES["quick"])

    prefix = profile.key.upper()
    overrides = {
        "max_searches": os.getenv(f"{prefix}_MAX_SEARCHES"),
        "research_max_tokens": os.getenv(f"{prefix}_RESEARCH_MAX_TOKENS"),
        "cache_hours": os.getenv(f"{prefix}_CACHE_HOURS"),
        "timeout_seconds": os.getenv(f"{prefix}_TIMEOUT_SECONDS"),
    }
    parsed = {
        key: int(value)
        for key, value in overrides.items()
        if value is not None and value.strip()
    }
    return replace(profile, **parsed) if parsed else profile
