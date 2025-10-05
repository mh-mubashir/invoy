import os, json
from typing import List, Dict

# Placeholder Claude integration with deterministic fallback
# In production, replace with Anthropic SDK call and strict JSON parsing

async def allocate_hours(client: str, total_hours: float, subjects: List[str], billing_period: str | None) -> Dict:
    if not subjects:
        return {"line_items": [], "confidence": 0.0}
    # Simple heuristic: weight by subject length
    weights = [max(1, len(s.split())) for s in subjects]
    ssum = float(sum(weights))
    raw = [total_hours * (w/ssum) for w in weights]
    # round to 0.1 hours and adjust last to match exactly
    rounded = [round(r*10)/10 for r in raw]
    diff = round(total_hours - sum(rounded), 1)
    if rounded:
        rounded[-1] = round(rounded[-1] + diff, 1)
    items = []
    for subject, hours in zip(subjects, rounded):
        items.append({
            "subject": subject.strip(),
            "estimated_hours": float(hours),
            "justification": "Proportional allocation based on subject complexity proxy."
        })
    return {
        "client_name": client,
        "total_hours_billed": float(total_hours),
        "billing_period": billing_period or "Monthly",
        "line_items": items,
        "confidence": 0.4
    }
