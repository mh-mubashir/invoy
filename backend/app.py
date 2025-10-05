from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from .stt import transcribe_audio
from .ai import allocate_hours
from .utils import finalize_invoice
from pathlib import Path
from dotenv import load_dotenv
import os
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from backend.calender_routes import router as calendar_router

# Load .env file from project root
load_dotenv(Path(__file__).resolve().parents[1] / '.env')

templates = Jinja2Templates(directory="templates")

app = FastAPI(title="Invoy Backend", version="0.1.0")

from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])

# Register routes
app.include_router(calendar_router, prefix="", tags=["Calendar"])

# app.mount("/assets", StaticFiles(directory="assets"), name="assets")
# @app.get("/", response_class=HTMLResponse)
# async def get_login_page(request: Request):
#     return templates.TemplateResponse("login.html", {"request": request})

# No-cache for HTML to always serve fresh UI
@app.middleware("http")
async def no_cache_html(request: Request, call_next):
    response: Response = await call_next(request)
    path = request.url.path or "/"
    if path.endswith(".html") or path == "/":
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response

class AllocateRequest(BaseModel):
    client: str | None = None
    total_hours: float | None = None
    work_subjects: list[str] | None = None
    freeform: str | None = None
    billing_period: str | None = None

@app.post("/stt")
async def stt_endpoint(file: UploadFile = File(...)):
    # Save the uploaded file temporarily
    temp_path = f"temp_{file.filename}"
    with open(temp_path, "wb") as f:
        f.write(await file.read())
        print("Saved uploaded file to:", temp_path)
    #Call the transcription function
    text = transcribe_audio(temp_path)

    # Remove temp file
    os.remove(temp_path)

    return {"text": text}

@app.post("/ai-invoice/allocate")
async def ai_allocate(req: AllocateRequest):
    from .ai import parse_freeform_with_claude
    if req.freeform:
        parsed = await parse_freeform_with_claude(req.freeform, req.client, req.total_hours)
        return JSONResponse(parsed)
    result = await allocate_hours(req.client or "Unknown Client", float(req.total_hours or 0), req.work_subjects or [], req.billing_period)
    return JSONResponse(result)

class FinalizeRequest(BaseModel):
    client: str
    line_items: list[dict]
    billing_period: str | None = None

@app.post("/ai-invoice/finalize")
async def finalize(req: FinalizeRequest):
    out = finalize_invoice(req.client, req.line_items, req.billing_period)
    return out

class SendEmailRequest(BaseModel):
    invoice_id: str
    recipient_email: str
    invoice_data: dict

@app.post("/ai-invoice/send-email")
async def send_email(req: SendEmailRequest):
    from .email import send_invoice_email
    from pathlib import Path
    ROOT = Path(__file__).resolve().parents[1]
    pdf_path = str(ROOT / 'output' / f"{req.invoice_id}.pdf")
    result = await send_invoice_email(req.invoice_data, pdf_path, req.recipient_email, req.invoice_data.get('consultant_email', ''))
    return result

# Mount static files AFTER API routes so they don't intercept API calls
# Serve project assets folder for logo (use different path to avoid conflict with Vite /assets)
app.mount('/static', StaticFiles(directory=str(Path(__file__).resolve().parents[1] / 'assets')), name='static')

# Serve output folder for invoice previews
app.mount('/invoices', StaticFiles(directory=str(Path(__file__).resolve().parents[1] / 'output')), name='invoices')

# Serve built web app at root (catch-all, must be last)
app.mount('/', StaticFiles(directory=str(Path(__file__).resolve().parents[1] / 'web' / 'dist'), html=True), name='root')
