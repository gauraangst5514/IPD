"""Conservative invoice-text extraction; no fabricated lines or price catalogue."""
import re
from decimal import Decimal

def parse_invoice(text):
    lines = []
    for raw in text.splitlines():
        # Explicit: description | quantity | unit price
        match = re.fullmatch(r"\s*([^|]+)\|\s*(\d+(?:\.\d+)?)\s*\|\s*(?:₹|Rs\.?|INR|\$)?\s*([\d,]+(?:\.\d{1,2})?)\s*", raw)
        if match:
            label, quantity, price = match.groups()
            amount = Decimal(quantity) * Decimal(price.replace(",", ""))
            lines.append({"description": label.strip(), "quantity": float(quantity),
                          "unit_price": float(Decimal(price.replace(",", ""))),
                          "line_total": float(amount)})
    total_match = re.search(r"(?:grand\s+total|invoice\s+total|total\s+amount)\s*[:=]?\s*(?:₹|Rs\.?|INR|\$)?\s*([\d,]+(?:\.\d{1,2})?)", text, re.I)
    declared = float(Decimal(total_match.group(1).replace(",", ""))) if total_match else None
    if not lines:
        return {"available": False, "reason": "No supported line items parsed. Use description | quantity | unit price.",
                "declared_total": declared, "lines": [], "indicators": []}
    calculated = sum(item["line_total"] for item in lines)
    return {"available": True, "method": "explicit_text_line_parser", "lines": lines,
            "declared_total": declared, "calculated_subtotal": calculated,
            "indicators": ([{"code": "invoice_total_difference", "status": "review",
                             "detail": "Parsed line subtotal differs from stated total. Verify taxes, discounts and missing lines."}]
                           if declared is not None and abs(calculated-declared) > .01 else []),
            "warning": "Arithmetic check only. Prices, authenticity and completeness are not verified."}
