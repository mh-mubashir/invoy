from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from .stt import transcribe_audio
from .ai import allocate_hours
from .utils import finalize_invoice
from pathlib import Path

app = FastAPI(title="Invoy Backend", version="0.1.0")

from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])
app.mount('/ui', StaticFiles(directory=str(Path(__file__).resolve().parents[1] / 'web/dist'), html=True), name='ui')


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
