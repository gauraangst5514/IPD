"""Observations and discrepancies are not fraud labels."""


def indicator(code, status, detail, evidence=None):
    return {"code": code, "status": status, "detail": detail, "evidence": evidence or {}}


def summarize(indicators):
    """Explicit review routing without a numerical fraud calculation."""
    return {
        "fraud_score": None,
        "score_type": "not_estimated",
        "fraud_indicators": indicators,
        "fraud_flags": list(dict.fromkeys(i["code"] for i in indicators if i["status"] == "review")),
        "review_required": any(i["status"] == "review" for i in indicators),
        "checks_complete": not any(i["status"] == "unavailable" for i in indicators),
    }
