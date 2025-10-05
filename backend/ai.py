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


async def generate_email_body(invoice_data: Dict) -> str:
    """Generate personalized email body for invoice delivery using Claude.
    Supports optional 'work_summary' to include custom summary of work performed.
    """
    # Load consultant name from config
    from pathlib import Path
    ROOT = Path(__file__).resolve().parents[1]
    try:
        config = json.loads((ROOT / 'data' / 'config.json').read_text())
        consultant_name = config.get('consultant', {}).get('name', 'Your Consultant')
    except:
        consultant_name = invoice_data.get('consultant_name', 'Your Consultant')
    
    if not _CLAUDE or not os.getenv('ANTHROPIC_API_KEY'):
        # Fallback email template
        work_summary = (invoice_data.get('work_summary') or '').strip()
        return f"""
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1f2937; line-height: 1.6;">
    <p>Hi {invoice_data.get('client_name', 'there')},</p>
    
    <p>I hope this message finds you well! I wanted to share the invoice for our recent work together during {invoice_data.get('billing_period', 'this period')}.</p>
    
    <p>It was a pleasure working on these projects with you. I'm really proud of what we accomplished together, and I'm looking forward to continuing our collaboration.</p>
    
    <p><strong>Invoice Summary:</strong><br>
    Total Hours: {invoice_data.get('total_hours', 0):.1f}<br>
    Total Amount: ${invoice_data.get('total_cost', 0):.2f}</p>
    {f"<p><strong>Work Summary:</strong><br>{work_summary}</p>" if work_summary else ""}
    
    <p>Please find the detailed invoice attached. If you have any questions or need clarification on any items, don't hesitate to reach out.</p>
    
    <p>Looking forward to our next project!</p>
    
    <p>Best regards,<br>
    {consultant_name}</p>
</body>
</html>
"""
    
    # Use Claude to generate personalized email
    client_api = anthropic.Anthropic()
    work_summary = (invoice_data.get('work_summary') or '').strip()
    prompt = f"""Write a warm, professional email to send an invoice to a client. 

Context:
- Client: {invoice_data.get('client_name')}
- Billing Period: {invoice_data.get('billing_period')}
- Total Hours: {invoice_data.get('total_hours')} 
- Total Cost: ${invoice_data.get('total_cost')}
- Work done: {len(invoice_data.get('line_items', []))} distinct tasks
- Custom work summary provided by the consultant (if any): {work_summary or 'N/A'}
- Consultant name (sign the email with this): {consultant_name}

Tone: Professional yet warm and personable, as if you personally worked with them and value the relationship.
Key points to include:
- Thank them for the opportunity to work together
- Briefly mention the amazing work accomplished
- Reference the attached invoice
- Express enthusiasm for continuing the partnership
- Keep it concise (3-4 short paragraphs)
- Sign the email with "{consultant_name}"

Return ONLY the HTML email body (no subject, no greetings like "Subject:"). Use simple HTML formatting."""

    resp = client_api.messages.create(
        model=os.getenv('ANTHROPIC_MODEL', 'claude-3-5-sonnet-20240620'),
        max_tokens=500,
        temperature=0.3,
        messages=[{"role": "user", "content": prompt}],
    )
    
    email_html = resp.content[0].text if getattr(resp, 'content', None) else ''
    return email_html if email_html else f"Please find attached invoice {invoice_data.get('invoice_id')} for {invoice_data.get('client_name')}."

