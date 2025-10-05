import os
import resend
from pathlib import Path
from typing import Dict

# Initialize Resend with API key from env
resend.api_key = os.getenv('RESEND_API_KEY')

async def send_invoice_email(invoice_data: Dict, pdf_path_str: str, recipient_email: str, consultant_email: str) -> Dict:
    """Send invoice via Resend with AI-generated email body"""
    if not os.getenv('RESEND_API_KEY'):
        return {'status': 'error', 'message': 'RESEND_API_KEY not configured'}
    
    try:
        # Construct full path
        ROOT = Path(__file__).resolve().parents[1]
        pdf_file = ROOT / 'output' / Path(pdf_path_str).name if not Path(pdf_path_str).is_absolute() else Path(pdf_path_str)
        
        if not pdf_file.exists():
            return {'status': 'error', 'message': f'PDF file not found: {pdf_file}'}
        
        # Generate personalized email body using Claude
        from .ai import generate_email_body
        email_body = await generate_email_body(invoice_data)
        
        # Send email via Resend
        params = {
            "from": f"Invoy <onboarding@resend.dev>",  # Update with your verified domain
            "to": [recipient_email],
            "subject": f"Invoice {invoice_data['invoice_id']} — {invoice_data['billing_period']}",
            "html": email_body,
            "attachments": [
                {
                    "filename": f"{invoice_data['invoice_id']}.pdf",
                    "content": list(pdf_file.read_bytes())
                }
            ]
        }
        
        email = resend.Emails.send(params)
        return {'status': 'ok', 'email_id': email.get('id'), 'recipient': recipient_email}
    
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

