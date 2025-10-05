from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from .stt import transcribe_audio
from .ai import allocate_hours
from .utils import finalize_invoice

app = FastAPI(title="Invoy Backend", version="0.1.0")

class AllocateRequest(BaseModel):
    client: str
    total_hours: float
    work_subjects: list[str]
    billing_period: str | None = None

@app.post("/stt")
async def stt_endpoint(file: UploadFile = File(...)):
    text = await transcribe_audio(file)
    return {"text": text}

@app.post("/ai-invoice/allocate")
async def ai_allocate(req: AllocateRequest):
    result = await allocate_hours(req.client, req.total_hours, req.work_subjects, req.billing_period)
    return JSONResponse(result)

class FinalizeRequest(BaseModel):
    client: str
    line_items: list[dict]
    billing_period: str | None = None

@app.post("/ai-invoice/finalize")
async def finalize(req: FinalizeRequest):
    out = finalize_invoice(req.client, req.line_items, req.billing_period)
    return out
