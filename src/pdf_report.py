from __future__ import annotations

from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .models import CompetitorProfile, IntelligenceReport, StrategicSignal

NAVY = colors.HexColor("#16243A")
TEAL = colors.HexColor("#247C82")
LIGHT = colors.HexColor("#EEF3F5")
MUTED = colors.HexColor("#5B6673")
BORDER = colors.HexColor("#D4DDE1")


def build_pdf(report: IntelligenceReport, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.65 * inch,
        bottomMargin=0.65 * inch,
        title=f"Competitive Intelligence: {report.target_company}",
        author="Competitive Intelligence Copilot",
    )
    styles = _styles()
    story: list[object] = [
        Paragraph("COMPETITIVE INTELLIGENCE", styles["eyebrow"]),
        Paragraph(escape(report.target_company), styles["title"]),
        Paragraph(
            f"Generated {escape(report.generated_at)} - "
            f"{escape(report.research_mode.title())} mode",
            styles["subtitle"],
        ),
        Spacer(1, 18),
        Paragraph("Executive summary", styles["h1"]),
        Paragraph(escape(report.executive_summary), styles["body"]),
        Spacer(1, 10),
        Paragraph("Market definition", styles["h1"]),
        Paragraph(escape(report.market_definition), styles["body"]),
        Spacer(1, 14),
        _competitor_overview(report, styles),
        PageBreak(),
    ]

    for index, competitor in enumerate(report.competitors):
        story.extend(_competitor_section(competitor, styles))
        if index < len(report.competitors) - 1:
            story.append(PageBreak())

    synthesis = _portfolio_synthesis(report, styles)
    if synthesis:
        story.extend([PageBreak(), *synthesis])

    story.extend(
        [
            Spacer(1, 12),
            Paragraph("Methodology and limitations", styles["h1"]),
            Paragraph(
                escape(report.methodology_and_limitations),
                styles["body"],
            ),
        ]
    )

    document.build(
        story,
        onFirstPage=_page_footer,
        onLaterPages=_page_footer,
    )
    return output_path


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "eyebrow": ParagraphStyle(
            "Eyebrow", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=8, textColor=TEAL, leading=10, spaceAfter=4,
        ),
        "title": ParagraphStyle(
            "Title", parent=base["Title"], fontName="Helvetica-Bold",
            fontSize=25, leading=29, textColor=NAVY, alignment=TA_CENTER,
            spaceAfter=6,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle", parent=base["Normal"], fontSize=9, leading=12,
            textColor=MUTED, alignment=TA_CENTER,
        ),
        "h1": ParagraphStyle(
            "H1", parent=base["Heading1"], fontName="Helvetica-Bold",
            fontSize=16, leading=20, textColor=NAVY, spaceBefore=4, spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "H2", parent=base["Heading2"], fontName="Helvetica-Bold",
            fontSize=11, leading=14, textColor=TEAL, spaceBefore=10, spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "Body", parent=base["BodyText"], fontName="Helvetica",
            fontSize=9, leading=13, textColor=NAVY, spaceAfter=5,
        ),
        "small": ParagraphStyle(
            "Small", parent=base["BodyText"], fontName="Helvetica",
            fontSize=7.5, leading=10, textColor=MUTED,
        ),
        "bullet": ParagraphStyle(
            "Bullet", parent=base["BodyText"], fontName="Helvetica",
            fontSize=8.5, leading=12, leftIndent=12, firstLineIndent=-7,
            bulletIndent=0, textColor=NAVY, spaceAfter=3,
        ),
    }


def _competitor_overview(
    report: IntelligenceReport,
    styles: dict[str, ParagraphStyle],
) -> Table:
    rows = [["Rank", "Competitor", "Overlap", "Why it matters"]]
    for competitor in report.competitors:
        rows.append(
            [
                str(competitor.rank),
                Paragraph(escape(competitor.name), styles["body"]),
                f"{competitor.overlap_score}/100",
                Paragraph(escape(competitor.why_it_matters), styles["small"]),
            ]
        )
    table = Table(
        rows,
        colWidths=[0.45 * inch, 1.35 * inch, 0.7 * inch, 4.15 * inch],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _competitor_section(
    competitor: CompetitorProfile,
    styles: dict[str, ParagraphStyle],
) -> list[object]:
    website = escape(competitor.website)
    story: list[object] = [
        Paragraph(f"#{competitor.rank} {escape(competitor.name)}", styles["h1"]),
        Paragraph(
            f"Overlap score: <b>{competitor.overlap_score}/100</b> - "
            f'Website: <link href="{website}">{website}</link>',
            styles["small"],
        ),
        Spacer(1, 8),
        Paragraph("Why it matters", styles["h2"]),
        Paragraph(escape(competitor.why_it_matters), styles["body"]),
    ]

    if competitor.positioning:
        story.extend(
            [
                Paragraph("Positioning", styles["h2"]),
                Paragraph(escape(competitor.positioning), styles["body"]),
            ]
        )

    _append_bullets(story, "Customer focus", competitor.customer_focus, styles)
    _append_bullets(
        story, "Evidence-backed differentiators",
        competitor.key_differentiators, styles,
    )

    signals = (
        competitor.recent_product_signals
        + competitor.leadership_and_hiring_signals
        + competitor.ecosystem_and_gtm_signals
    )
    if signals:
        story.append(Paragraph("Strategic signals", styles["h2"]))
        story.extend(_signals(signals, styles))

    _append_bullets(story, "Threats to the target company", competitor.threats, styles)
    _append_bullets(
        story, "Openings for the target company", competitor.opportunities, styles
    )

    if competitor.evidence:
        story.append(Paragraph("Sources and verified claims", styles["h2"]))
        for evidence in competitor.evidence:
            url = escape(evidence.source_url)
            story.append(
                Paragraph(
                    "• "
                    f"<b>{escape(evidence.claim)}</b> "
                    f"({escape(evidence.confidence.value)} confidence) - "
                    f'<link href="{url}">{escape(evidence.source_title)}</link>'
                    f", {escape(evidence.published_date)}",
                    styles["small"],
                )
            )
    return story


def _signals(
    signals: list[StrategicSignal],
    styles: dict[str, ParagraphStyle],
) -> list[KeepTogether]:
    blocks: list[KeepTogether] = []
    for signal in signals:
        source_text = ", ".join(
            f'<link href="{escape(url)}">source</link>'
            for url in signal.source_urls
        )
        content: list[object] = [
            Paragraph(
                f"<b>{escape(signal.title)}</b> - "
                f"{escape(signal.date)} - "
                f"{escape(signal.confidence.value)} confidence",
                styles["body"],
            ),
            Paragraph(escape(signal.summary), styles["small"]),
        ]
        if signal.strategic_implication:
            content.append(
                Paragraph(
                    "<b>Implication:</b> "
                    f"{escape(signal.strategic_implication)}"
                    + (f" - {source_text}" if source_text else ""),
                    styles["small"],
                )
            )
        elif source_text:
            content.append(Paragraph(source_text, styles["small"]))
        content.append(Spacer(1, 5))
        blocks.append(KeepTogether(content))
    return blocks


def _append_bullets(
    story: list[object],
    title: str,
    items: list[str],
    styles: dict[str, ParagraphStyle],
) -> None:
    clean_items = [item for item in items if item.strip()]
    if not clean_items:
        return
    content: list[object] = [Paragraph(escape(title), styles["h2"])]
    content.extend(
        Paragraph(f"• {escape(item)}", styles["bullet"])
        for item in clean_items
    )
    story.append(KeepTogether(content))


def _portfolio_synthesis(
    report: IntelligenceReport,
    styles: dict[str, ParagraphStyle],
) -> list[object]:
    sections = [
        ("Cross-competitor themes", report.cross_competitor_themes),
        ("Whitespace opportunities", report.whitespace_opportunities),
        ("Strategic threats", report.strategic_threats),
        ("Recommended actions", report.recommended_actions),
        ("Watchlist", report.watchlist),
    ]
    if not any(items for _title, items in sections):
        return []

    story: list[object] = [Paragraph("Portfolio-level synthesis", styles["h1"])]
    for title, items in sections:
        _append_bullets(story, title, items, styles)
    return story


def _page_footer(canvas: object, document: object) -> None:
    canvas.saveState()
    canvas.setStrokeColor(BORDER)
    canvas.line(0.65 * inch, 0.48 * inch, 7.85 * inch, 0.48 * inch)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(
        0.65 * inch,
        0.3 * inch,
        "Competitive Intelligence Copilot - Public-source research",
    )
    canvas.drawRightString(7.85 * inch, 0.3 * inch, f"Page {document.page}")
    canvas.restoreState()
