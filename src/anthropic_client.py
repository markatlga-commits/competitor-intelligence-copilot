from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from .config import ResearchProfile, Settings
from .models import (
    CompetitorProfile,
    Confidence,
    IntelligenceReport,
    SignalType,
    SourceEvidence,
    StrategicSignal,
)
from .prompts import RESEARCH_SYSTEM_PROMPT, build_research_prompt
from .usage import RunUsage, StageUsage


class ResearchError(RuntimeError):
    """Raised when competitive research cannot be completed safely."""


@dataclass(frozen=True, slots=True)
class SourceRecord:
    source_id: str
    title: str
    url: str
    cited_text: str
    published_date: str = ""


@dataclass(frozen=True, slots=True)
class LedgerSignal:
    date: str
    signal_type: SignalType
    title: str
    fact: str
    implication: str
    confidence: Confidence
    source_hint: str


@dataclass(frozen=True, slots=True)
class LedgerCompetitor:
    name: str
    website: str
    overlap_score: int
    why_it_matters: str
    positioning: str
    customer_focus: tuple[str, ...]
    differentiators: tuple[str, ...]
    signals: tuple[LedgerSignal, ...]
    threats: tuple[str, ...]
    opportunities: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ResearchLedger:
    target_description: str
    executive_summary: str
    market_definition: str
    competitors: tuple[LedgerCompetitor, ...]
    themes: tuple[str, ...]
    whitespace: tuple[str, ...]
    strategic_threats: tuple[str, ...]
    recommended_actions: tuple[str, ...]
    watchlist: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ClaudeRunResult:
    report: IntelligenceReport
    usage: RunUsage
    notes: str
    sources: tuple[SourceRecord, ...]


ProgressCallback = Callable[[str], None]


class ClaudeResearchClient:
    def __init__(self, settings: Settings, profile: ResearchProfile) -> None:
        if not settings.api_key_configured:
            raise ResearchError(
                "ANTHROPIC_API_KEY is not configured. Add your personal key "
                "as a Codespaces secret or in a local .env file."
            )

        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise ResearchError(
                "The anthropic package is not installed. Run "
                "python -m pip install -r requirements.txt."
            ) from exc

        self.settings = settings
        self.profile = profile
        self.client = Anthropic(
            api_key=settings.anthropic_api_key,
            timeout=float(profile.timeout_seconds),
            max_retries=2,
        )

    def run(
        self,
        company_name: str,
        progress: ProgressCallback | None = None,
    ) -> ClaudeRunResult:
        notify = progress or (lambda _message: None)
        notify("Researching current competitor activity and strategic implications")
        notes, sources, research_usage = self._research_notes(company_name)

        notify("Building and validating the evidence-backed report")
        ledger = parse_research_ledger(notes, sources=sources)
        report = build_report_from_ledger(
            company_name=company_name,
            generated_at=datetime.now(UTC).isoformat(),
            mode=self.profile.key,
            ledger=ledger,
            sources=sources,
        )
        return ClaudeRunResult(
            report=report,
            usage=RunUsage((research_usage,)),
            notes=notes,
            sources=sources,
        )

    def _research_notes(
        self,
        company_name: str,
    ) -> tuple[str, tuple[SourceRecord, ...], StageUsage]:
        messages: list[dict[str, Any]] = [
            {
                "role": "user",
                "content": build_research_prompt(company_name, self.profile),
            }
        ]
        tool: dict[str, Any] = {
            "type": self.settings.web_search_tool,
            "name": "web_search",
            "max_uses": self.profile.max_searches,
            "allowed_callers": ["direct"],
            "user_location": {
                "type": "approximate",
                "country": "US",
                "timezone": "America/New_York",
            },
        }
        tool_version = self.settings.web_search_tool.rsplit("_", 1)[-1]
        if tool_version.isdigit() and int(tool_version) >= 20260318:
            tool["response_inclusion"] = "full"

        responses: list[Any] = []
        stage_usage = StageUsage(
            stage="research",
            model=self.settings.research_model,
        )

        for _attempt in range(self.settings.max_continuations):
            request: dict[str, Any] = {
                "model": self.settings.research_model,
                "max_tokens": self.profile.research_max_tokens,
                "system": [
                    {
                        "type": "text",
                        "text": RESEARCH_SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                "messages": messages,
                "tools": [tool],
                "output_config": {"effort": self.profile.effort},
                "stop_sequences": ["END_RESEARCH"],
                "thinking": {"type": "disabled"},
            }
            if not responses:
                request["tool_choice"] = {"type": "any"}

            response = self.client.messages.create(**request)
            responses.append(response)
            stage_usage = _merge_usage(
                stage_usage,
                _usage_from_response(
                    response,
                    stage="research",
                    model=self.settings.research_model,
                ),
            )

            if response.stop_reason == "pause_turn":
                messages.append({"role": "assistant", "content": response.content})
                continue
            break
        else:
            raise ResearchError(
                "Claude paused the research too many times. Run the report again."
            )

        final_response = responses[-1]
        if final_response.stop_reason == "refusal":
            raise ResearchError("Claude declined the research request.")

        notes, sources = extract_notes_and_sources(responses)
        if not notes.strip():
            raise ResearchError("Claude returned no research notes.")
        if not sources:
            search_errors = extract_web_search_errors(responses)
            if search_errors:
                raise ResearchError(
                    "Claude web search did not return usable sources: "
                    + ", ".join(search_errors)
                    + ". Run the report again."
                )
            raise ResearchError(
                "Claude searched the web but returned no usable source URLs. "
                "Run the report again."
            )
        if final_response.stop_reason == "max_tokens":
            raise ResearchError(
                "Claude's research response ended before the final sentence "
                "was complete. Run the report again or select Balanced mode."
            )
        return notes, sources, stage_usage


_SIGNAL_ALIASES = {
    "product": SignalType.PRODUCT,
    "product_release": SignalType.PRODUCT,
    "release": SignalType.PRODUCT,
    "leadership": SignalType.LEADERSHIP,
    "executive": SignalType.LEADERSHIP,
    "hiring": SignalType.HIRING,
    "partnership": SignalType.PARTNERSHIP,
    "partner": SignalType.PARTNERSHIP,
    "pricing": SignalType.PRICING,
    "packaging": SignalType.PRICING,
    "go_to_market": SignalType.GO_TO_MARKET,
    "go-to-market": SignalType.GO_TO_MARKET,
    "gtm": SignalType.GO_TO_MARKET,
    "acquisition": SignalType.ACQUISITION,
    "documentation": SignalType.DOCUMENTATION,
    "docs": SignalType.DOCUMENTATION,
    "inference": SignalType.INFERENCE,
}

_STOPWORDS = {
    "about", "after", "also", "and", "are", "company", "from", "have",
    "into", "more", "that", "the", "their", "this", "through", "with",
    "will", "your", "platform", "product", "services", "official",
}


def parse_research_ledger(
    notes: str,
    sources: tuple[SourceRecord, ...] = (),
) -> ResearchLedger:
    global_fields: dict[str, str] = {}
    themes: list[str] = []
    whitespace: list[str] = []
    strategic_threats: list[str] = []
    recommended_actions: list[str] = []
    watchlist: list[str] = []
    competitors: list[LedgerCompetitor] = []
    current: dict[str, Any] | None = None

    def finish_current() -> None:
        nonlocal current
        if current is None:
            return
        name = _clean_text(current.get("name", ""))
        if name:
            signals = tuple(current.get("signals", []))
            if not signals:
                signals = _recover_signals_from_sources(
                    name=name,
                    website=_normalize_website(current.get("website", "")),
                    sources=sources,
                )
            competitors.append(
                LedgerCompetitor(
                    name=name,
                    website=_normalize_website(current.get("website", "")),
                    overlap_score=_bounded_int(current.get("overlap", 50), 0, 100),
                    why_it_matters=_complete_sentence(
                        current.get("why_it_matters", current.get("why", ""))
                    ),
                    positioning=_complete_sentence(
                        current.get("positioning", "")
                    ),
                    customer_focus=tuple(
                        _unique_nonempty(current.get("customer_focus", []))
                    )[:3],
                    differentiators=tuple(
                        _unique_sentences(current.get("differentiators", []))
                    )[:4],
                    signals=signals[:5],
                    threats=tuple(
                        _unique_sentences(current.get("threats", []))
                    )[:3],
                    opportunities=tuple(
                        _unique_sentences(current.get("opportunities", []))
                    )[:3],
                )
            )
        current = None

    for raw_line in notes.replace("\r", "").splitlines():
        line = _normalize_ledger_line(raw_line)
        if not line:
            continue
        upper = line.upper()

        if upper.startswith("COMPETITOR_START"):
            finish_current()
            current = {
                "customer_focus": [],
                "differentiators": [],
                "signals": [],
                "threats": [],
                "opportunities": [],
            }
            continue
        if upper.startswith("COMPETITOR_END"):
            finish_current()
            continue
        if upper.startswith("END_RESEARCH") or upper.startswith("SEARCH SOURCES"):
            finish_current()
            break

        if current is not None:
            match = re.match(
                r"^(NAME|WEBSITE|OVERLAP|WHY_IT_MATTERS|WHY|POSITIONING|"
                r"CUSTOMER_FOCUS|DIFFERENTIATOR|SIGNAL|EVIDENCE|THREAT|"
                r"OPPORTUNITY)\s*:\s*(.*)$",
                line,
                re.I,
            )
            if not match:
                continue
            key, value = match.groups()
            key = key.casefold()
            value = _clean_text(value)
            if key in {"customer_focus", "differentiator", "threat", "opportunity"}:
                destination = {
                    "customer_focus": "customer_focus",
                    "differentiator": "differentiators",
                    "threat": "threats",
                    "opportunity": "opportunities",
                }[key]
                if value:
                    current[destination].append(value)
                continue
            if key in {"signal", "evidence"}:
                signal = _parse_signal_line(value)
                if signal is not None:
                    current["signals"].append(signal)
                continue
            current[key] = value
            continue

        match = re.match(
            r"^(TARGET|EXECUTIVE_SUMMARY|MARKET_DEFINITION|THEME|WHITESPACE|"
            r"STRATEGIC_THREAT|RECOMMENDED_ACTION|WATCH_ITEM)\s*:\s*(.*)$",
            line,
            re.I,
        )
        if not match:
            continue
        key, value = match.groups()
        key = key.casefold()
        value = _clean_text(value)
        if not value:
            continue
        if key in {"target", "executive_summary", "market_definition"}:
            global_fields[key] = _complete_sentence(value)
        elif key == "theme":
            themes.append(_complete_sentence(value))
        elif key == "whitespace":
            whitespace.append(_complete_sentence(value))
        elif key == "strategic_threat":
            strategic_threats.append(_complete_sentence(value))
        elif key == "recommended_action":
            recommended_actions.append(_complete_sentence(value))
        elif key == "watch_item":
            watchlist.append(
                _complete_sentence(
                    re.sub(r"\s*\|\|\s*", " - ", value)
                )
            )

    finish_current()

    unique: list[LedgerCompetitor] = []
    seen: set[str] = set()
    for competitor in competitors:
        key = competitor.name.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(competitor)
        if len(unique) == 3:
            break

    if len(unique) != 3:
        raise ResearchError(
            "Claude did not return three distinct competitor profiles. "
            "Run the report again or select Balanced mode."
        )
    if any(not competitor.signals for competitor in unique):
        raise ResearchError(
            "The research did not include source-backed signals for all three "
            "competitors. Run the report again."
        )

    return ResearchLedger(
        target_description=global_fields.get("target", ""),
        executive_summary=global_fields.get("executive_summary", ""),
        market_definition=global_fields.get("market_definition", ""),
        competitors=tuple(unique),
        themes=tuple(_unique_nonempty(themes))[:5],
        whitespace=tuple(_unique_nonempty(whitespace))[:5],
        strategic_threats=tuple(_unique_nonempty(strategic_threats))[:5],
        recommended_actions=tuple(_unique_nonempty(recommended_actions))[:6],
        watchlist=tuple(_unique_nonempty(watchlist))[:5],
    )


def _normalize_ledger_line(value: str) -> str:
    cleaned = _remove_source_marker(value.strip())
    cleaned = re.sub(r"^[#>]+\s*", "", cleaned)
    cleaned = re.sub(r"^[-*•]\s+", "", cleaned)
    cleaned = re.sub(r"^\d+[.)]\s*", "", cleaned)
    cleaned = cleaned.replace("**", "").replace("__", "").replace("`", "")
    return cleaned.strip()


def _parse_signal_line(value: str) -> LedgerSignal | None:
    cleaned = _clean_text(value)
    delimiter = r"\s*\|\|\s*" if "||" in cleaned else r"\s*\|\s*"
    parts = [part.strip() for part in re.split(delimiter, cleaned)]

    if len(parts) >= 7:
        date, signal_type, title, fact, implication, confidence, source_hint = parts[:7]
    elif len(parts) == 6:
        date, signal_type, title, fact, implication, confidence = parts
        source_hint = ""
    elif len(parts) == 5:
        date, signal_type, fact, implication, confidence = parts
        title = _signal_title(fact)
        source_hint = ""
    else:
        return None

    fact = _clean_text(fact)
    if not fact:
        return None
    return LedgerSignal(
        date=_clean_text(date) or "Recent",
        signal_type=_signal_type(signal_type),
        title=_clean_text(title) or _signal_title(fact),
        fact=_complete_sentence(fact),
        implication=_complete_sentence(implication),
        confidence=_confidence(confidence),
        source_hint=_clean_text(source_hint),
    )


def _recover_signals_from_sources(
    name: str,
    website: str,
    sources: tuple[SourceRecord, ...],
) -> tuple[LedgerSignal, ...]:
    if not sources:
        return ()

    website_host = urlparse(website).netloc.casefold().removeprefix("www.")
    name_tokens = _meaningful_tokens(name)

    def score(source: SourceRecord) -> int:
        haystack = " ".join([source.title, source.url, source.cited_text]).casefold()
        points = 0
        if name.casefold() in haystack:
            points += 40
        source_host = urlparse(source.url).netloc.casefold().removeprefix("www.")
        if website_host and (
            website_host == source_host or website_host in source_host
        ):
            points += 35
        points += 5 * sum(token in haystack for token in name_tokens)
        return points

    ranked = sorted(sources, key=score, reverse=True)
    selected = [source for source in ranked if score(source) > 0][:2]
    recovered: list[LedgerSignal] = []
    for source in selected:
        fact = _source_fact(source)
        if not fact:
            continue
        recovered.append(
            LedgerSignal(
                date=source.published_date or "Recent",
                signal_type=_infer_signal_type(
                    f"{source.title} {source.cited_text}"
                ),
                title=_signal_title(source.title or fact),
                fact=fact,
                implication="",
                confidence=Confidence.HIGH if source.cited_text else Confidence.MEDIUM,
                source_hint=source.title,
            )
        )
    return tuple(recovered)


def build_report_from_ledger(
    company_name: str,
    generated_at: str,
    mode: str,
    ledger: ResearchLedger,
    sources: tuple[SourceRecord, ...],
) -> IntelligenceReport:
    source_usage: Counter[str] = Counter()
    profiles: list[CompetitorProfile] = []

    for rank, competitor in enumerate(ledger.competitors, start=1):
        profiles.append(
            _build_competitor_profile(
                rank=rank,
                competitor=competitor,
                sources=sources,
                source_usage=source_usage,
            )
        )

    executive_summary = ledger.executive_summary or _grounded_summary(profiles)
    market_definition = (
        ledger.market_definition
        or ledger.target_description
        or f"{company_name} competes in the market reflected by the cited sources."
    )

    return IntelligenceReport(
        target_company=company_name,
        generated_at=generated_at,
        research_mode=mode,
        executive_summary=executive_summary,
        market_definition=market_definition,
        competitors=profiles,
        cross_competitor_themes=list(ledger.themes),
        whitespace_opportunities=list(ledger.whitespace),
        strategic_threats=list(ledger.strategic_threats),
        recommended_actions=list(ledger.recommended_actions),
        watchlist=list(ledger.watchlist),
        methodology_and_limitations=(
            "This assessment is based on current public web sources. Facts are "
            "separated from strategic interpretation, and unsupported sections "
            "are omitted. Public evidence may be incomplete and does not confirm "
            "private company roadmaps."
        ),
    )


def _build_competitor_profile(
    rank: int,
    competitor: LedgerCompetitor,
    sources: tuple[SourceRecord, ...],
    source_usage: Counter[str],
) -> CompetitorProfile:
    source_evidence: list[SourceEvidence] = []
    signals: list[StrategicSignal] = []

    for item in competitor.signals:
        source = _best_source(competitor, item, sources, source_usage)
        source_evidence.append(
            SourceEvidence(
                claim=item.fact,
                source_title=source.title,
                source_url=source.url,
                published_date=item.date,
                confidence=item.confidence,
            )
        )
        signals.append(
            StrategicSignal(
                title=item.title,
                signal_type=item.signal_type,
                date=item.date,
                summary=item.fact,
                strategic_implication=item.implication,
                confidence=item.confidence,
                source_urls=[source.url],
            )
        )

    product_types = {SignalType.PRODUCT, SignalType.DOCUMENTATION}
    leadership_types = {SignalType.LEADERSHIP, SignalType.HIRING}
    ecosystem_types = {
        SignalType.PARTNERSHIP,
        SignalType.PRICING,
        SignalType.GO_TO_MARKET,
        SignalType.ACQUISITION,
        SignalType.INFERENCE,
    }

    first_fact = competitor.signals[0].fact if competitor.signals else ""
    why_it_matters = competitor.why_it_matters or (
        f"{competitor.name}: {first_fact}" if first_fact else competitor.name
    )
    positioning = competitor.positioning or why_it_matters

    return CompetitorProfile(
        rank=rank,
        name=competitor.name,
        website=competitor.website or source_evidence[0].source_url,
        overlap_score=competitor.overlap_score,
        why_it_matters=why_it_matters,
        positioning=positioning,
        customer_focus=list(competitor.customer_focus),
        key_differentiators=list(competitor.differentiators),
        recent_product_signals=[
            signal for signal in signals if signal.signal_type in product_types
        ],
        leadership_and_hiring_signals=[
            signal for signal in signals if signal.signal_type in leadership_types
        ],
        ecosystem_and_gtm_signals=[
            signal for signal in signals if signal.signal_type in ecosystem_types
        ],
        threats=list(competitor.threats),
        opportunities=list(competitor.opportunities),
        evidence=source_evidence,
    )


def _grounded_summary(profiles: list[CompetitorProfile]) -> str:
    sentences: list[str] = []
    for profile in profiles:
        if profile.evidence:
            sentences.append(
                f"{profile.name}: {profile.evidence[0].claim.rstrip('.')}."
            )
    return " ".join(sentences)


def _best_source(
    competitor: LedgerCompetitor,
    signal: LedgerSignal,
    sources: tuple[SourceRecord, ...],
    usage: Counter[str],
) -> SourceRecord:
    if not sources:
        raise ResearchError("No source was available for the report.")

    website_host = urlparse(competitor.website).netloc.casefold().removeprefix("www.")
    name_tokens = _meaningful_tokens(competitor.name)
    fact_tokens = _meaningful_tokens(signal.fact)
    hint_tokens = _meaningful_tokens(signal.source_hint)

    def score(source: SourceRecord) -> tuple[int, int]:
        haystack = " ".join(
            [source.title, source.url, source.cited_text]
        ).casefold()
        points = 0
        if competitor.name.casefold() in haystack:
            points += 35
        source_host = urlparse(source.url).netloc.casefold().removeprefix("www.")
        if website_host and (
            website_host == source_host or website_host in source_host
        ):
            points += 30
        points += 8 * sum(token in haystack for token in hint_tokens)
        points += 4 * sum(token in haystack for token in name_tokens)
        points += 2 * sum(token in haystack for token in fact_tokens)
        return points, -usage[source.url]

    selected = max(sources, key=score)
    usage[selected.url] += 1
    return selected


def _source_fact(source: SourceRecord) -> str:
    cited = _clean_text(source.cited_text)
    if cited:
        match = re.search(r"^.*?[.!?](?=\s|$)", cited)
        if match:
            return _complete_sentence(match.group(0))
    return _complete_sentence(source.title)


def _infer_signal_type(value: str) -> SignalType:
    normalized = value.casefold()
    keyword_map = (
        (SignalType.HIRING, ("hiring", "job", "career", "recruit")),
        (SignalType.LEADERSHIP, ("ceo", "chief", "president", "appoint")),
        (SignalType.PARTNERSHIP, ("partner", "alliance", "ecosystem")),
        (SignalType.PRICING, ("pricing", "price", "package", "edition")),
        (SignalType.ACQUISITION, ("acquire", "acquisition", "merger")),
        (SignalType.DOCUMENTATION, ("documentation", "developer", "api docs")),
        (SignalType.GO_TO_MARKET, ("launch", "market", "sales", "channel")),
    )
    for signal_type, keywords in keyword_map:
        if any(keyword in normalized for keyword in keywords):
            return signal_type
    return SignalType.PRODUCT


def _complete_sentence(value: object) -> str:
    text = _clean_text(value)
    if not text:
        return ""

    text = re.sub(r"(?:\.{3}|…)+$", "", text).rstrip()
    if not text:
        return ""

    if re.search(r'[.!?][\"\')\]]?$', text):
        return text
    return text + "."


def _unique_sentences(values: list[str]) -> list[str]:
    return list(
        dict.fromkeys(
            sentence
            for value in values
            if (sentence := _complete_sentence(value))
        )
    )


def _unique_nonempty(values: list[str]) -> list[str]:
    return list(
        dict.fromkeys(_clean_text(value) for value in values if _clean_text(value))
    )


def _meaningful_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.casefold())
        if len(token) >= 4 and token not in _STOPWORDS
    }


def _signal_title(value: str) -> str:
    compact = _clean_text(value).rstrip(".")
    words = compact.split()
    if len(words) <= 14:
        return compact
    return " ".join(words[:14])


def _normalize_website(value: str) -> str:
    cleaned = _clean_text(value)
    if not cleaned:
        return ""
    return cleaned if cleaned.startswith(("http://", "https://")) else "https://" + cleaned


def _bounded_int(value: object, minimum: int, maximum: int) -> int:
    match = re.search(r"-?\d+", str(value))
    parsed = int(match.group()) if match else minimum
    return max(minimum, min(maximum, parsed))


def _signal_type(value: str) -> SignalType:
    normalized = _clean_text(value).casefold().replace(" ", "_")
    return _SIGNAL_ALIASES.get(normalized, SignalType.INFERENCE)


def _confidence(value: str) -> Confidence:
    normalized = _clean_text(value).casefold()
    if normalized == "high":
        return Confidence.HIGH
    if normalized == "medium":
        return Confidence.MEDIUM
    return Confidence.LOW


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").split())


def _remove_source_marker(value: str) -> str:
    return re.sub(r"\s*\[Sources?:[^\]]+\]\s*", " ", value, flags=re.I).strip()


def extract_notes_and_sources(
    responses: list[Any],
) -> tuple[str, tuple[SourceRecord, ...]]:
    source_by_url: dict[str, SourceRecord] = {}
    note_parts: list[str] = []
    cited_source_ids: set[str] = set()

    def add_source(
        url: str,
        title: str = "Untitled source",
        cited_text: str = "",
        published_date: str = "",
    ) -> SourceRecord | None:
        normalized_url = str(url or "").strip()
        if not normalized_url:
            return None
        existing = source_by_url.get(normalized_url)
        if existing is not None:
            if not existing.cited_text and cited_text:
                updated = SourceRecord(
                    source_id=existing.source_id,
                    title=title or existing.title,
                    url=existing.url,
                    cited_text=str(cited_text).strip(),
                    published_date=(
                        str(published_date).strip() or existing.published_date
                    ),
                )
                source_by_url[normalized_url] = updated
                return updated
            return existing
        source = SourceRecord(
            source_id=f"S{len(source_by_url) + 1}",
            title=str(title or "Untitled source").strip(),
            url=normalized_url,
            cited_text=str(cited_text or "").strip(),
            published_date=str(published_date or "").strip(),
        )
        source_by_url[normalized_url] = source
        return source

    for response in responses:
        for block in getattr(response, "content", []):
            if getattr(block, "type", None) != "web_search_tool_result":
                continue
            content = getattr(block, "content", None)
            if not isinstance(content, list):
                continue
            for result in content:
                if getattr(result, "type", None) != "web_search_result":
                    continue
                add_source(
                    url=getattr(result, "url", ""),
                    title=getattr(result, "title", "Untitled source"),
                    cited_text=getattr(result, "cited_text", ""),
                    published_date=getattr(result, "page_age", ""),
                )

    for response in responses:
        for block in getattr(response, "content", []):
            if getattr(block, "type", None) != "text":
                continue
            text = str(getattr(block, "text", "") or "").strip()
            if not text:
                continue
            block_source_ids: list[str] = []
            for citation in getattr(block, "citations", []) or []:
                source = add_source(
                    url=getattr(citation, "url", ""),
                    title=getattr(citation, "title", "Untitled source"),
                    cited_text=getattr(citation, "cited_text", ""),
                    published_date=getattr(citation, "page_age", ""),
                )
                if source is None:
                    continue
                block_source_ids.append(source.source_id)
                cited_source_ids.add(source.source_id)
            if block_source_ids:
                markers = ", ".join(dict.fromkeys(block_source_ids))
                note_parts.append(f"{text}\n[Sources: {markers}]")
            else:
                note_parts.append(text)

    if source_by_url and not cited_source_ids:
        catalog = "\n".join(
            f"[{source.source_id}] {source.title} | {source.url}"
            for source in source_by_url.values()
        )
        note_parts.append("SEARCH SOURCES RETRIEVED\n" + catalog)

    return "\n\n".join(note_parts), tuple(source_by_url.values())


def extract_web_search_errors(responses: list[Any]) -> tuple[str, ...]:
    errors: list[str] = []
    for response in responses:
        for block in getattr(response, "content", []):
            if getattr(block, "type", None) != "web_search_tool_result":
                continue
            content = getattr(block, "content", None)
            if getattr(content, "type", None) != "web_search_tool_result_error":
                continue
            code = str(getattr(content, "error_code", "unknown") or "unknown")
            if code not in errors:
                errors.append(code)
    return tuple(errors)


def _usage_from_response(response: Any, stage: str, model: str) -> StageUsage:
    usage = getattr(response, "usage", None)
    server_usage = getattr(usage, "server_tool_use", None)
    return StageUsage(
        stage=stage,
        model=model,
        input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
        output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
        cache_creation_input_tokens=int(
            getattr(usage, "cache_creation_input_tokens", 0) or 0
        ),
        cache_read_input_tokens=int(
            getattr(usage, "cache_read_input_tokens", 0) or 0
        ),
        web_search_requests=int(
            getattr(server_usage, "web_search_requests", 0) or 0
        ),
    )


def _merge_usage(left: StageUsage, right: StageUsage) -> StageUsage:
    return StageUsage(
        stage=left.stage,
        model=left.model,
        input_tokens=left.input_tokens + right.input_tokens,
        output_tokens=left.output_tokens + right.output_tokens,
        cache_creation_input_tokens=(
            left.cache_creation_input_tokens + right.cache_creation_input_tokens
        ),
        cache_read_input_tokens=(
            left.cache_read_input_tokens + right.cache_read_input_tokens
        ),
        web_search_requests=left.web_search_requests + right.web_search_requests,
    )
