import os
import resend
from pathlib import Path
from typing import Dict
import base64

# Initialize Resend with API key from env
resend.api_key = os.getenv('RESEND_API_KEY')

async def send_invoice_email(invoice_data: Dict, pdf_path_str: str, recipient_email: str, consultant_email: str) -> Dict:
    """Send invoice via Resend with AI-generated email body"""
    print(f"\n{'='*60}")
    print(f"📧 EMAIL SENDING ATTEMPT")
    print(f"{'='*60}")
    
    api_key = os.getenv('RESEND_API_KEY')
    if not api_key:
        print("❌ RESEND_API_KEY not set in environment")
        return {'status': 'error', 'message': 'RESEND_API_KEY not configured'}
    
    print(f"✓ Resend API key found: {api_key[:10]}...")
    
    try:
        # Construct full path
        ROOT = Path(__file__).resolve().parents[1]
        pdf_file = ROOT / 'output' / Path(pdf_path_str).name if not Path(pdf_path_str).is_absolute() else Path(pdf_path_str)
        
        print(f"📎 PDF path: {pdf_file}")
        if not pdf_file.exists():
            print(f"❌ PDF file not found!")
            return {'status': 'error', 'message': f'PDF file not found: {pdf_file}'}
        
        print(f"✓ PDF file exists ({pdf_file.stat().st_size} bytes)")
        
        # Generate personalized email body using Claude
        print("✍️  Generating email body with Claude...")
        from .ai import generate_email_body
        email_body = await generate_email_body(invoice_data)
        print(f"✓ Email body generated ({len(email_body)} chars)")
        
        # Send email via Resend
        from_email = os.getenv('RESEND_FROM_EMAIL', 'onboarding@resend.dev')
        
        # Check if domain is verified (if not using resend.dev default)
        if 'resend.dev' not in from_email:
            print(f"📧 Using verified domain email: {from_email}")
            actual_recipient = recipient_email
        else:
            # Fallback to testing mode
            verified_email = os.getenv('RESEND_VERIFIED_EMAIL', 'mmqpak2015@gmail.com')
            actual_recipient = verified_email
            print(f"⚠️  Testing mode: sending to {verified_email} instead of {recipient_email}")
            print(f"   To send to any email, verify your domain at resend.com/domains")
        
        print(f"📨 Sending to: {actual_recipient}")
        
        params = {
            "from": f"Invoy <{from_email}>",
            "to": [actual_recipient],
            "subject": f"Invoice {invoice_data['invoice_id']} — {invoice_data['billing_period']}",
            "html": email_body,
            "attachments": [
                {
                    "filename": f"{invoice_data['invoice_id']}.pdf",
                    # Resend expects base64-encoded content string
                    "content": base64.b64encode(pdf_file.read_bytes()).decode("ascii")
                }
            ]
        }
        
        print(f"🚀 Calling Resend API...")
        email = resend.Emails.send(params)
        print(f"✅ Email sent successfully!")
        print(f"   Email ID: {email.get('id')}")
        print(f"   Recipient: {recipient_email}")
        print(f"{'='*60}\n")
        return {'status': 'ok', 'email_id': email.get('id'), 'recipient': recipient_email}
    
    except Exception as e:
        print(f"❌ Error sending email: {type(e).__name__}: {str(e)}")
        print(f"{'='*60}\n")
        import traceback
        traceback.print_exc()
        return {'status': 'error', 'message': str(e)}

