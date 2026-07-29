"""
Email Notification Service

Sends email notifications when claim status changes.
Uses Python's built-in smtplib + email modules.

Falls back gracefully to console logging if SMTP is not configured.
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _is_smtp_configured() -> bool:
    """Check if SMTP settings are configured."""
    settings = get_settings()
    return bool(settings.SMTP_HOST and settings.SMTP_PORT and settings.SMTP_FROM)


def _build_html_body(claim_id: str, status: str, details: dict) -> str:
    """Build an HTML email body for claim status notification."""
    status_colors = {
        "submitted": "#3b82f6",
        "processing": "#f59e0b",
        "awaiting_review": "#8b5cf6",
        "approved": "#10b981",
        "rejected": "#ef4444",
        "flagged": "#f97316",
    }
    color = status_colors.get(status, "#6b7280")

    damage_summary = details.get("damage_summary", "N/A")
    cost_min = details.get("cost_estimate_min")
    cost_max = details.get("cost_estimate_max")
    cost_display = f"₹{cost_min:,.0f} - ₹{cost_max:,.0f}" if cost_min and cost_max else "Pending"
    severity = details.get("severity", "N/A")
    fraud_score = details.get("fraud_risk_score")
    fraud_display = f"{fraud_score:.0%}" if fraud_score is not None else "N/A"
    notes = details.get("notes", "")

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f9fafb; }}
            .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
            .header {{ background: #1e293b; padding: 24px; text-align: center; }}
            .header h1 {{ color: white; margin: 0; font-size: 20px; }}
            .content {{ padding: 24px; }}
            .status-badge {{ display: inline-block; padding: 6px 16px; border-radius: 20px; color: white; background: {color}; font-weight: 600; font-size: 14px; text-transform: uppercase; }}
            .details-table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
            .details-table td {{ padding: 10px 0; border-bottom: 1px solid #e5e7eb; }}
            .details-table td:first-child {{ font-weight: 600; color: #374151; width: 40%; }}
            .details-table td:last-child {{ color: #6b7280; }}
            .footer {{ padding: 16px 24px; background: #f9fafb; text-align: center; font-size: 12px; color: #9ca3af; }}
            .notes {{ background: #f3f4f6; padding: 12px; border-radius: 6px; margin-top: 16px; font-size: 14px; color: #4b5563; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>IntelliClaim</h1>
            </div>
            <div class="content">
                <p>Your claim status has been updated:</p>

                <p><strong>Claim ID:</strong> {claim_id[:8]}...</p>
                <p><strong>Status:</strong> <span class="status-badge">{status.replace('_', ' ').title()}</span></p>

                <table class="details-table">
                    <tr><td>Damage Type</td><td>{damage_summary}</td></tr>
                    <tr><td>Severity</td><td>{severity.title()}</td></tr>
                    <tr><td>Estimated Cost</td><td>{cost_display}</td></tr>
                    <tr><td>Fraud Risk</td><td>{fraud_display}</td></tr>
                </table>

                {"<div class='notes'><strong>Assessor Notes:</strong> " + notes + "</div>" if notes else ""}
            </div>
            <div class="footer">
                <p>This is an automated notification from IntelliClaim. Do not reply to this email.</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html


def _get_subject(claim_id: str, status: str) -> str:
    """Generate email subject line based on status."""
    subjects = {
        "submitted": "Claim Submitted Successfully",
        "processing": "Your Claim is Being Processed",
        "awaiting_review": "Claim Processing Complete - Under Review",
        "approved": "Claim Approved",
        "rejected": "Claim Update - Decision Made",
        "flagged": "Claim Requires Additional Review",
    }
    short_id = claim_id[:8]
    subject_text = subjects.get(status, "Claim Status Update")
    return f"[IntelliClaim] {subject_text} ({short_id})"


def send_claim_notification(
    email: str,
    claim_id: str,
    status: str,
    details: Optional[dict] = None,
) -> bool:
    """
    Send an email notification about claim status change.

    Args:
        email: Recipient email address
        claim_id: The claim's UUID string
        status: New claim status (submitted, processing, approved, rejected, flagged, etc.)
        details: Optional dict with damage_summary, cost_estimate_min, cost_estimate_max,
                 severity, fraud_risk_score, notes

    Returns:
        True if email was sent (or logged), False on error.
    """
    if details is None:
        details = {}

    subject = _get_subject(claim_id, status)
    html_body = _build_html_body(claim_id, status, details)

    if not _is_smtp_configured():
        # Fallback: log to console
        logger.info(
            f"📧 [NOTIFICATION] To: {email} | Subject: {subject} | "
            f"Claim: {claim_id} | Status: {status}"
        )
        print(
            f"📧 [EMAIL NOT SENT - SMTP not configured] "
            f"To: {email}, Subject: {subject}"
        )
        return True

    settings = get_settings()

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM
        msg["To"] = email

        # Plain text fallback
        plain_text = (
            f"IntelliClaim - Claim Status Update\n\n"
            f"Claim ID: {claim_id}\n"
            f"Status: {status.replace('_', ' ').title()}\n"
            f"Damage: {details.get('damage_summary', 'N/A')}\n"
            f"Severity: {details.get('severity', 'N/A')}\n"
        )
        if details.get("cost_estimate_min") and details.get("cost_estimate_max"):
            plain_text += (
                f"Estimated Cost: ₹{details['cost_estimate_min']:,.0f} - "
                f"₹{details['cost_estimate_max']:,.0f}\n"
            )

        msg.attach(MIMEText(plain_text, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        # Connect and send
        if settings.SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT)
        else:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
            server.starttls()

        if settings.SMTP_USER and settings.SMTP_PASSWORD:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)

        server.sendmail(settings.SMTP_FROM, [email], msg.as_string())
        server.quit()

        logger.info(f"📧 Email sent to {email} for claim {claim_id} (status: {status})")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to send email to {email}: {e}")
        print(f"❌ [EMAIL ERROR] Failed to send to {email}: {e}")
        return False
