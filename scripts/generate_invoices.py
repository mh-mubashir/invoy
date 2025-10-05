#!/usr/bin/env python3
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from dateutil import parser as dtp
from jinja2 import Environment, FileSystemLoader, select_autoescape
import pytz

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
TEMPLATES = ROOT / 'templates'
OUTPUT = ROOT / 'output'


def load_config():
    cfg = json.loads((DATA / 'config.json').read_text())
    return cfg['consultant'], cfg['branding'], cfg['rules']


class Event:
    def __init__(self, d):
        self.id = d['id']
        self.title = d['title']
        self.description = d.get('description', '')
        self.start = d['start']
        self.end = d['end']
        self.status = d.get('status', 'confirmed')
        self.attendees = d.get('attendees', [])

    @property
    def duration_hours(self):
        start = dtp.parse(self.start)
        end = dtp.parse(self.end)
        return max(0.0, (end - start).total_seconds() / 3600.0)


def parse_calendar_txt(text: str):
    blocks = re.split(r"\n\s*Event:\n", text, flags=re.M)
    events = []
    for b in blocks:
        b = b.strip()
        if not b or b.startswith('#'):
            continue
        def get(pattern):
            m = re.search(pattern, b, flags=re.M)
            return m.group(1).strip() if m else None
        id_ = get(r"^\s*id:\s*(.+)$")
        title = get(r"^\s*title:\s*(.+)$")
        description = get(r"^\s*description:\s*(.+)$")
        start = get(r"^\s*start:\s*(.+)$")
        end = get(r"^\s*end:\s*(.+)$")
        status = get(r"^\s*status:\s*(.+)$") or 'confirmed'
        attendees = []
        for entry in re.finditer(r"-\s*name:\s*(.+)\n\s*email:\s*(.+)", b, flags=re.M):
            attendees.append({'name': entry.group(1).strip(), 'email': entry.group(2).strip()})
        if id_ and title and start and end:
            events.append(Event({
                'id': id_, 'title': title, 'description': description or '',
                'start': start, 'end': end, 'status': status, 'attendees': attendees
            }))
    return events


def is_billable(event: Event, rules, consultant_email: str):
    if any(k.lower() in event.title.lower() for k in [k.lower() for k in rules['excludeKeywordsInTitle']]):
        return False
    if event.status != 'confirmed':
        return False
    if event.duration_hours * 60 < rules['minDurationMinutes']:
        return False
    others = [a for a in event.attendees if a['email'].lower() != consultant_email.lower()]
    return len(others) > 0


def identify_client(event: Event, consultant_email: str):
    others = [a for a in event.attendees if a['email'].lower() != consultant_email.lower()]
    if not others:
        return None
    a = others[0]
    return {'name': a.get('name') or a['email'], 'email': a['email'], 'company': None}


def render_invoice(consultant, branding, client_key, client_info, items, period_start, period_end):
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=select_autoescape(['html','xml']))
    tmpl = env.get_template('invoice.html.j2')
    rate = float(consultant['hourlyRate'])
    for it in items:
        it['rate'] = rate
        it['amount'] = round(it['durationHours'] * rate, 2)
    subtotal = round(sum(i['amount'] for i in items), 2)
    tax_rate = float(consultant.get('taxRate', 0.0))
    tax_amount = round(subtotal * tax_rate, 2)
    total_due = round(subtotal + tax_amount, 2)

    invoice = {
        'invoiceId': f"INV-{client_key}-{period_start[:7].replace('-', '')}",
        'issueDate': datetime.now(timezone.utc).date().isoformat(),
        'billingPeriodStart': period_start,
        'billingPeriodEnd': period_end
    }

    currency_symbol = {'USD':'$','EUR':'€','GBP':'£'}.get(consultant['currency'], '')
    html = tmpl.render(
        consultant=consultant,
        branding=branding,
        client=client_info,
        invoice=invoice,
        items=items,
        totals={'subtotal': subtotal, 'taxAmount': tax_amount, 'totalDue': total_due},
        currencySymbol=currency_symbol
    )
    OUTPUT.mkdir(parents=True, exist_ok=True)
    out = OUTPUT / f"{invoice['invoiceId']}.html"
    out.write_text(html)
    return out


def main():
    parser = argparse.ArgumentParser(description='Generate invoice HTML from calendar txt sample.')
    parser.add_argument('--input', default=str(DATA / 'calendar_sample.txt'), help='Path to calendar txt')
    args = parser.parse_args()

    consultant, branding, rules = load_config()
    txt = Path(args.input).read_text()
    events = parse_calendar_txt(txt)
    billable = [e for e in events if is_billable(e, rules, consultant['email'])]

    m = re.search(r"Billing Period:\s*(\d{4}-\d{2}-\d{2})\s*to\s*(\d{4}-\d{2}-\d{2})", txt)
    if m:
        period_start, period_end = m.group(1), m.group(2)
    else:
        period_start = events[0].start[:10]
        period_end = events[-1].end[:10]

    by_client = {}
    for e in billable:
        client = identify_client(e, consultant['email'])
        if not client:
            continue
        key = client['email'].lower()
        by_client.setdefault(key, {'info': client, 'items': []})
        start = dtp.parse(e.start)
        end = dtp.parse(e.end)
        tz = pytz.timezone(consultant['timezone'])
        start_local = start.astimezone(tz)
        end_local = end.astimezone(tz)
        by_client[key]['items'].append({
            'date': start_local.strftime('%Y-%m-%d'),
            'timeRange': f"{start_local.strftime('%H:%M')}–{end_local.strftime('%H:%M')}",
            'subject': e.title,
            'agenda': (e.description or '').split('Agenda:')[-1].strip() if 'Agenda:' in (e.description or '') else '',
            'durationHours': e.duration_hours
        })

    generated = []
    for key, data in by_client.items():
        out = render_invoice(consultant, branding, key.replace('@','_').replace('.', '-'), data['info'], data['items'], period_start, period_end)
        generated.append(str(out))

    print('Generated invoices:', *generated, sep='\n - ')


if __name__ == '__main__':
    main()
