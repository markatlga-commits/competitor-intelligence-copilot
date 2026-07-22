from __future__ import annotations

from .config import ResearchProfile

RESEARCH_SYSTEM_PROMPT = """
You are a senior product manager. Use current public web
information to create a concise, evidence-backed executive assessment.

Research standards:
- Prefer first-party product pages, documentation, release notes, official
  newsrooms, investor relations, partner directories, pricing pages, executive
  biographies, and current job postings.
- Use reputable independent reporting only when first-party evidence is
  unavailable.
- Focus on developments from the last 12 months, except for durable market
  positioning.
- Never invent companies, facts, dates, sources, customer segments, or
  strategic implications.
- Distinguish verified facts from inference.
- Every conclusion must be traceable to the researched evidence.

Quality standards:
- Be specific. Name products, capabilities, partnerships, leadership moves,
  customer segments, or go-to-market actions.
- Explain why each development matters to the target company.
- Do not use generic phrases such as "monitor the market," "differentiate on
  customer outcomes," or "warrants continued monitoring" unless paired with a
  specific evidence-backed action.
- Do not fill a section merely because it exists. Omit unsupported items.

Output standards:
- You MUST use web search before writing.
- Return exactly three distinct competitors.
- Return plain text only using the requested labels and delimiters.
- Keep every labeled field on one line.
- Every prose field must contain complete sentences and end with proper punctuation.
- Never use ellipses and never stop in the middle of a sentence.
- Do not return JSON, XML, Markdown tables, code fences, or a preamble.
- End with END_RESEARCH on its own line.
""".strip()


MODE_LIMITS = {
    "quick": {
        "word_limit": 1050,
        "signals": 2,
        "customers": 1,
        "differentiators": 2,
        "threats": 1,
        "opportunities": 1,
        "themes": 2,
        "whitespace": 2,
        "actions": 3,
    },
    "balanced": {
        "word_limit": 1550,
        "signals": 3,
        "customers": 2,
        "differentiators": 3,
        "threats": 2,
        "opportunities": 2,
        "themes": 3,
        "whitespace": 3,
        "actions": 4,
    },
    "deep": {
        "word_limit": 2100,
        "signals": 5,
        "customers": 3,
        "differentiators": 4,
        "threats": 3,
        "opportunities": 3,
        "themes": 4,
        "whitespace": 4,
        "actions": 5,
    },
}


def build_research_prompt(company_name: str, profile: ResearchProfile) -> str:
    limits = MODE_LIMITS[profile.key]
    return f"""
Research the company named exactly: {company_name}

Use no more than {profile.max_searches} broad web searches and no more than
{limits['word_limit']} words total.

Return this exact format:

TARGET: one evidence-backed sentence describing what {company_name} sells, its primary customers, and the market in which it competes
EXECUTIVE_SUMMARY: two concise sentences naming the most important competitive findings and their implications for {company_name}
MARKET_DEFINITION: one concise sentence defining the relevant competitive market

COMPETITOR_START
NAME: official company name
WEBSITE: official homepage URL
OVERLAP: integer from 0 to 100
WHY_IT_MATTERS: one specific sentence explaining direct competitive relevance
POSITIONING: one specific sentence describing how the competitor positions itself and the outcome it promises
CUSTOMER_FOCUS: specific customer segment or buyer
DIFFERENTIATOR: one complete sentence describing a specific capability, distribution advantage, operating model, data asset, ecosystem advantage, or commercial distinction
SIGNAL: DATE || SIGNAL_TYPE || SHORT TITLE || ONE COMPLETE VERIFIED-FACT SENTENCE || ONE COMPLETE TARGET-COMPANY-IMPLICATION SENTENCE || CONFIDENCE || SOURCE TITLE OR DOMAIN
THREAT: one evidence-backed threat to {company_name}
OPPORTUNITY: one evidence-backed opening for {company_name}
COMPETITOR_END

Repeat COMPETITOR_START through COMPETITOR_END exactly three times.

THEME: one specific pattern supported by at least two competitors
WHITESPACE: one specific unmet need or strategic opening grounded in the evidence
STRATEGIC_THREAT: one specific portfolio-level threat grounded in the evidence
RECOMMENDED_ACTION: one concrete action {company_name} should take, including what to investigate, build, package, partner on, or validate
WATCH_ITEM: competitor name || specific future signal to watch
END_RESEARCH

Rules:
- Exactly {limits['signals']} SIGNAL lines per competitor.
- Up to {limits['customers']} CUSTOMER_FOCUS lines per competitor.
- Exactly {limits['differentiators']} DIFFERENTIATOR lines per competitor.
- Exactly {limits['threats']} THREAT lines per competitor.
- Exactly {limits['opportunities']} OPPORTUNITY lines per competitor.
- Exactly {limits['themes']} THEME lines.
- Exactly {limits['whitespace']} WHITESPACE lines.
- Exactly {limits['actions']} RECOMMENDED_ACTION lines.
- Include one STRATEGIC_THREAT and one WATCH_ITEM per competitor.
- SIGNAL_TYPE must be one of: product, leadership, hiring, partnership, pricing, go_to_market, acquisition, documentation, inference.
- CONFIDENCE must be high, medium, or low.
- SOURCE TITLE OR DOMAIN should identify the source used for that signal.
- Cite TARGET, EXECUTIVE_SUMMARY, MARKET_DEFINITION, every SIGNAL, every THEME, every WHITESPACE, every STRATEGIC_THREAT, every RECOMMENDED_ACTION, and every WATCH_ITEM.
- Keep each field concise and substantive.
- Before returning, verify that every narrative field ends at a natural sentence boundary.
""".strip()
