from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from .stt import transcribe_audio
from .ai import allocate_hours
from .utils import finalize_invoice
from pathlib import Path
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from backend.calender_routes import router as calendar_router

templates = Jinja2Templates(directory="templates")

app = FastAPI(title="Invoy Backend", version="0.1.0")

app.mount("/assets", StaticFiles(directory="assets"), name="assets")

from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])

# Register routes
app.include_router(calendar_router, prefix="", tags=["Calendar"])

# Example route to render the login page
@app.get("/", response_class=HTMLResponse)
async def get_login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

# No-cache for HTML to always serve fresh UI
@app.middleware("http")
async def no_cache_html(request: Request, call_next):
    response: Response = await call_next(request)
    path = request.url.path or "/"
    if path.endswith(".html") or path == "/":
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response

# Serve built web app at root
app.mount('/', StaticFiles(directory=str(Path(__file__).resolve().parents[1] / 'web' / 'dist'), html=True), name='root')


class AllocateRequest(BaseModel):
    client: str | None = None
    total_hours: float | None = None
    work_subjects: list[str] | None = None
    freeform: str | None = None
    billing_period: str | None = None

@app.post("/stt")
async def stt_endpoint(file: UploadFile = File(...)):
    text = await transcribe_audio(file)
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
