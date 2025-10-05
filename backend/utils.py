import json
from pathlib import Path
from typing import List, Dict

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'
OUTPUT = ROOT / 'output'

# Finalize invoice by calling the existing generator path with prepared items
# For now, we just compute amounts and write a minimal HTML using the template pipeline later.

def finalize_invoice(client: str, line_items: List[Dict], billing_period: str | None):
    # Prepare a simple response consistent with frontend expectations
    total_hours = sum(float(i.get('estimated_hours') or i.get('hours', 0)) for i in line_items)
    return {
        'client': client,
        'total_hours': round(total_hours, 2),
        'line_items': line_items,
        'status': 'ok'
    }
