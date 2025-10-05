import os, json, re
from typing import List, Dict, Optional

try:
    import anthropic
    _CLAUDE = True
except Exception:
    _CLAUDE = False

SCHEMA_INSTRUCTIONS = (
    "You are Invoy's AI Billing Allocation Expert. "
    "Extract client name (if present), total billable hours, and a list of subjects from free-form text. "
    "Then distribute the total hours across the subjects. Use JSON only."
)

OUTPUT_FORMAT = {
    "client_name": "string",
    "total_hours_billed": 0.0,
    "billing_period": "Monthly",
    "line_items": [
        {"subject": "string", "estimated_hours": 0.0, "justification": "string"}
    ],
    "confidence": 0.0
}


def _heuristic_parse_freeform(text: str) -> Dict:
    # Try to find hours number in text
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:h|hrs|hours)", text, re.I)
    total = float(m.group(1)) if m else 0.0
    # Split subjects by lines or punctuation
    lines = [s.strip(" -•\n\t") for s in re.split(r"[\n;]", text) if s.strip()]
    # Remove lines that look like hours mention
    subjects = [l for l in lines if not re.search(r"\bhours?\b", l, re.I)]
    subjects = subjects[:10] if subjects else [text[:60] + ('…' if len(text) > 60 else '')]
    return {"client_name": None, "total_hours_billed": total, "subjects": subjects}


async def parse_freeform_with_claude(freeform: str, default_client: Optional[str], default_hours: Optional[float]) -> Dict:
    if not _CLAUDE or not os.getenv('ANTHROPIC_API_KEY'):
        # fallback to heuristic only
        parsed = _heuristic_parse_freeform(freeform)
        client = parsed.get('client_name') or (default_client or 'Unknown Client')
        total = parsed.get('total_hours_billed') or (default_hours or 0.0)
        return {
            "client_name": client,
            "total_hours_billed": float(total),
            "billing_period": "Monthly",
            "line_items": [
                {"subject": s, "estimated_hours": round(float(total)/(len(parsed['subjects']) or 1), 1), "justification": "Even split (fallback)"}
                for s in parsed['subjects']
            ],
            "confidence": 0.2
        }

    client = anthropic.Anthropic()
    prompt = (
        SCHEMA_INSTRUCTIONS + "\n\n"
        + "Freeform input:\n" + freeform + "\n\n"
        + "Constraints:\n"
        + "- Sum of estimated_hours must equal total_hours_billed.\n"
        + "- JSON only, no prose.\n"
        + "If client name or total hours are missing, infer from context or set to defaults.\n"
        + f"Defaults: client={default_client or 'Unknown Client'}, total_hours={default_hours or 0.0}.\n"
        + "JSON schema keys: client_name, total_hours_billed, billing_period, line_items[{subject, estimated_hours, justification}], confidence.\n"
    )
    resp = client.messages.create(
        model=os.getenv('ANTHROPIC_MODEL', 'claude-3-5-sonnet-20240620'),
        max_tokens=1024,
        temperature=0.2,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text if getattr(resp, 'content', None) else ''
    try:
        data = json.loads(text)
    except Exception:
        # try to extract JSON block
        m = re.search(r"\{[\s\S]*\}", text)
        data = json.loads(m.group(0)) if m else None
    if not data:
        return await parse_freeform_with_claude(freeform, default_client, default_hours)  # fallback heuristic
    # normalize
    total = float(data.get('total_hours_billed') or default_hours or 0.0)
    items = data.get('line_items') or []
    # Adjust rounding to 0.1 and normalize sum
    if items:
        vals = [round(float(i.get('estimated_hours', 0.0))*10)/10 for i in items]
        diff = round(total - sum(vals), 1)
        if vals:
            vals[-1] = round(vals[-1] + diff, 1)
        for i, v in zip(items, vals):
            i['estimated_hours'] = float(v)
    return {
        "client_name": data.get('client_name') or (default_client or 'Unknown Client'),
        "total_hours_billed": total,
        "billing_period": data.get('billing_period') or 'Monthly',
        "line_items": items,
        "confidence": float(data.get('confidence') or 0.6)
    }

async def allocate_hours(client: str, total_hours: float, subjects: List[str], billing_period: str | None) -> Dict:
    # Existing deterministic allocation for structured input
    if subjects:
        weights = [max(1, len(s.split())) for s in subjects]
        ssum = float(sum(weights))
        raw = [total_hours * (w/ssum) for w in weights]
        rounded = [round(r*10)/10 for r in raw]
        diff = round(total_hours - sum(rounded), 1)
        if rounded:
            rounded[-1] = round(rounded[-1] + diff, 1)
        items = [{"subject": s.strip(), "estimated_hours": float(h), "justification": "Proportional allocation."} for s, h in zip(subjects, rounded)]
        return {"client_name": client, "total_hours_billed": float(total_hours), "billing_period": billing_period or "Monthly", "line_items": items, "confidence": 0.4}
    # No subjects provided: treat `client` as default client, and `total_hours` may be 0; expect caller to pass freeform in 'client' or separate param.
    return {"client_name": client, "total_hours_billed": float(total_hours), "billing_period": billing_period or "Monthly", "line_items": [], "confidence": 0.0}
