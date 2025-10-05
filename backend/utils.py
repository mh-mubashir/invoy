import json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
import json
from typing import List, Dict

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'
OUTPUT = ROOT / 'output'

# Finalize invoice by calling the existing generator path with prepared items
# For now, we just compute amounts and write a minimal HTML using the template pipeline later.

def finalize_invoice(client: str, line_items: List[Dict], billing_period: str | None):
    # Render AI-assist invoice using a dedicated template
    ROOT = Path(__file__).resolve().parents[1]
    DATA = ROOT / 'data'
    TEMPLATES = ROOT / 'templates'
    OUTPUT = ROOT / 'output'
    config = json.loads((DATA / 'config.json').read_text())
    consultant = config['consultant']; branding = config['branding']
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=select_autoescape(['html','xml']))
    tmpl = env.get_template('invoice_ai.html.j2')
    rate = float(consultant['hourlyRate'])
    items = []
    for it in line_items:
        hours = float(it.get('estimated_hours') or it.get('hours') or 0)
        amount = round(hours * rate, 2)
        items.append({'subject': it.get('subject',''), 'justification': it.get('justification',''), 'hours': hours, 'rate': rate, 'amount': amount})
    subtotal = round(sum(i['amount'] for i in items), 2)
    tax_rate = float(consultant.get('taxRate', 0.0))
    tax_amount = round(subtotal * tax_rate, 2)
    total_due = round(subtotal + tax_amount, 2)
    invoice_id = f"AI-{client.replace('@','_').replace('.','-').replace(' ','-')}"
    import datetime
    invoice = { 'invoiceId': invoice_id, 'issueDate': datetime.date.today().isoformat(), 'billingPeriod': billing_period or 'Monthly' }
    total_hours = sum(i['hours'] for i in items)
    html = tmpl.render(consultant=consultant, branding=branding, client={'name': client, 'email': ''}, invoice=invoice, aiSummary=f'AI-assisted allocation from freeform input on {invoice["issueDate"]}', items=items, totals={'subtotal': subtotal, 'taxAmount': tax_amount, 'totalDue': total_due}, currencySymbol={'USD':'$','EUR':'€','GBP':'£'}.get(consultant['currency'], ''))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    out = OUTPUT / f"{invoice_id}.html"
    out.write_text(html)
    # Return full metadata for frontend
    return {
        'status':'ok',
        'invoice_id': invoice_id,
        'path': f'/invoices/{invoice_id}.html',
        'client_name': client,
        'total_hours': round(total_hours, 2),
        'total_cost': total_due,
        'billing_period': billing_period or 'Monthly',
        'line_items': line_items
    }
