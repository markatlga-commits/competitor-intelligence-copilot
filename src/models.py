from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SignalType(StrEnum):
    PRODUCT = "product"
    LEADERSHIP = "leadership"
    HIRING = "hiring"
    PARTNERSHIP = "partnership"
    PRICING = "pricing"
    GO_TO_MARKET = "go_to_market"
    ACQUISITION = "acquisition"
    DOCUMENTATION = "documentation"
    INFERENCE = "inference"


class SourceEvidence(StrictModel):
    claim: str
    source_title: str
    source_url: str
    published_date: str
    confidence: Confidence


class StrategicSignal(StrictModel):
    title: str
    signal_type: SignalType
    date: str
    summary: str
    strategic_implication: str
    confidence: Confidence
    source_urls: list[str]


class CompetitorProfile(StrictModel):
    rank: int = Field(ge=1, le=3)
    name: str
    website: str
    overlap_score: int = Field(ge=0, le=100)
    why_it_matters: str
    positioning: str
    customer_focus: list[str]
    key_differentiators: list[str]
    recent_product_signals: list[StrategicSignal]
    leadership_and_hiring_signals: list[StrategicSignal]
    ecosystem_and_gtm_signals: list[StrategicSignal]
    threats: list[str]
    opportunities: list[str]
    evidence: list[SourceEvidence]


class IntelligenceReport(StrictModel):
    target_company: str
    generated_at: str
    research_mode: str
    executive_summary: str
    market_definition: str
    competitors: list[CompetitorProfile] = Field(min_length=3, max_length=3)
    cross_competitor_themes: list[str]
    whitespace_opportunities: list[str]
    strategic_threats: list[str]
    recommended_actions: list[str]
    watchlist: list[str]
    methodology_and_limitations: str

    @model_validator(mode="after")
    def validate_competitor_set(self) -> IntelligenceReport:
        ranks = [competitor.rank for competitor in self.competitors]
        names = [competitor.name.casefold() for competitor in self.competitors]
        if ranks != [1, 2, 3]:
            raise ValueError("Competitor ranks must be exactly 1 through 3.")
        if len(set(names)) != 3:
            raise ValueError("Competitor names must be unique.")
        return self

    @property
    def source_count(self) -> int:
        urls = {
            evidence.source_url
            for competitor in self.competitors
            for evidence in competitor.evidence
            if evidence.source_url
        }
        return len(urls)
