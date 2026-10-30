"""
Claim PDF Report Generator

Generates a downloadable PDF report for a processed claim,
including AI assessment results, cost breakdown, fraud analysis,
and image thumbnails.
"""

import io
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image as RLImage
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT


# Colors
PRIMARY = HexColor("#1e40af")
GRAY = HexColor("#6b7280")
LIGHT_GRAY = HexColor("#f3f4f6")
RED = HexColor("#dc2626")
GREEN = HexColor("#16a34a")
ORANGE = HexColor("#ea580c")
WHITE = HexColor("#ffffff")


def generate_claim_pdf(claim: dict, images: list[dict] = None) -> bytes:
    """
    Generate a PDF report for a claim.

    Args:
        claim: Dict with claim data (from get_claim endpoint response)
        images: Optional list of image dicts with paths for thumbnails

    Returns:
        PDF file as bytes
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="Title2",
        parent=styles["Title"],
        fontSize=20,
        textColor=PRIMARY,
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="SectionHeader",
        parent=styles["Heading2"],
        fontSize=13,
        textColor=PRIMARY,
        spaceBefore=14,
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="SmallGray",
        parent=styles["Normal"],
        fontSize=8,
        textColor=GRAY,
    ))

    elements = []

    # ─── Header ───────────────────────────────────────────────
    elements.append(Paragraph("IntelliClaim", styles["Title2"]))
    elements.append(Paragraph("AI-Powered Vehicle Damage Assessment Report", styles["SmallGray"]))
    elements.append(Spacer(1, 4 * mm))
    elements.append(HRFlowable(width="100%", thickness=1, color=PRIMARY))
    elements.append(Spacer(1, 6 * mm))

    # ─── Claim Info ───────────────────────────────────────────
    elements.append(Paragraph("Claim Information", styles["SectionHeader"]))

    status = claim.get("status", "unknown").replace("_", " ").title()
    status_color = GREEN if status == "Approved" else RED if status == "Rejected" else ORANGE

    info_data = [
        ["Claim ID", claim.get("id", "N/A")],
        ["Status", status],
        ["Filed On", _format_date(claim.get("created_at"))],
        ["Processed On", _format_date(claim.get("processed_at"))],
        ["Incident Location", claim.get("incident_location") or "Not specified"],
        ["Description", claim.get("description") or "Not provided"],
    ]

    info_table = Table(info_data, colWidths=[4.5 * cm, 12 * cm])
    info_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), GRAY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 4 * mm))

    # ─── AI Assessment ────────────────────────────────────────
    if claim.get("damage_type"):
        elements.append(Paragraph("AI Assessment", styles["SectionHeader"]))

        assessment_data = [
            ["Damage Type", (claim.get("damage_type") or "").title()],
            ["Estimated Severity", (claim.get("severity") or "Not assessed").title()],
            ["Detection Confidence", f"{claim['confidence_score'] * 100:.1f}%" if claim.get("confidence_score") is not None else "Not assessed"],
        ]

        assess_table = Table(assessment_data, colWidths=[4.5 * cm, 12 * cm])
        assess_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TEXTCOLOR", (0, 0), (0, -1), GRAY),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(assess_table)
        elements.append(Spacer(1, 4 * mm))

    # ─── Cost Estimate ────────────────────────────────────────
    if claim.get("estimated_cost_min"):
        elements.append(Paragraph("Indicative Repair-Cost Band", styles["SectionHeader"]))

        cost_min = claim.get("estimated_cost_min", 0)
        cost_max = claim.get("estimated_cost_max", 0)
        breakdown = claim.get("cost_breakdown") or {}

        cost_data = [
            ["Estimated Range", f"₹{cost_min:,.0f} – ₹{cost_max:,.0f}"],
            ["Parts", f"₹{breakdown.get('parts', 0):,.0f}"],
            ["Labour", f"₹{breakdown.get('labour', 0):,.0f}"],
            ["Paint", f"₹{breakdown.get('paint', 0):,.0f}"],
        ]

        cost_table = Table(cost_data, colWidths=[4.5 * cm, 12 * cm])
        cost_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (1, 0), (1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TEXTCOLOR", (0, 0), (0, -1), GRAY),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(cost_table)
        elements.append(Spacer(1, 4 * mm))

    # Evidence observations replace the legacy uncalibrated risk percentage.
    from xml.sax.saxutils import escape
    elements.append(Paragraph("Claim Evidence Review", styles["SectionHeader"]))
    elements.append(Paragraph("Fraud probability has not been estimated.", styles["Normal"]))
    indicators = (claim.get("fraud_flags") or {}).get("_indicators", [])
    if not indicators:
        elements.append(Paragraph("Reprocess this claim to generate evidence indicators.", styles["Normal"]))
    for item in indicators:
        text = f"{item.get('code', '').replace('_', ' ')} [{item.get('status', 'unavailable')}]: {item.get('detail', '')}"
        elements.append(Paragraph(escape(text), styles["Normal"]))
        for match in item.get("evidence", {}).get("matches", []):
            detail = f"Matching claim: {match['claim_id']}; image: {match['image_id']}; type: {match['match_type']}"
            elements.append(Paragraph(escape(detail), styles["Normal"]))
    elements.append(Spacer(1, 4 * mm))

    # ─── Images Summary ───────────────────────────────────────
    claim_images = claim.get("images") or []
    if claim_images:
        elements.append(Paragraph("Uploaded Images", styles["SectionHeader"]))

        img_data = [["#", "Damage Type", "Severity", "Confidence", "Manipulated"]]
        for i, img in enumerate(claim_images, 1):
            img_data.append([
                str(i),
                (img.get("damage_type") or "—").title(),
                (img.get("severity") or "—").title(),
                f"{img['confidence'] * 100:.0f}%" if img.get("confidence") is not None else "Not assessed",
                "Not assessed" if img.get("is_manipulated") is None else "Yes" if img["is_manipulated"] else "No",
            ])

        img_table = Table(img_data, colWidths=[1.5 * cm, 4 * cm, 3 * cm, 3 * cm, 3 * cm])
        img_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, 0), (-1, 0), LIGHT_GRAY),
            ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#e5e7eb")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
        ]))
        elements.append(img_table)
        elements.append(Spacer(1, 4 * mm))

    # ─── Footer ───────────────────────────────────────────────
    elements.append(Spacer(1, 10 * mm))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=GRAY))
    elements.append(Spacer(1, 3 * mm))
    elements.append(Paragraph(
        f"Generated by IntelliClaim AI on {datetime.now().strftime('%d %b %Y, %H:%M')} | "
        f"This report is auto-generated and should be reviewed by a qualified assessor.",
        styles["SmallGray"],
    ))

    # Build PDF
    doc.build(elements)
    return buffer.getvalue()


def _format_date(dt) -> str:
    """Format a datetime or ISO string for display."""
    if not dt:
        return "N/A"
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return dt
    if isinstance(dt, datetime):
        return dt.strftime("%d %b %Y, %H:%M")
    return str(dt)
