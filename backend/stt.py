import io
from fastapi import UploadFile

# Optional Vosk import guarded
try:
    from vosk import Model, KaldiRecognizer
    import soundfile as sf
    _VOSK_AVAILABLE = True
except Exception:
    _VOSK_AVAILABLE = False

_model = None

def _load_model():
    global _model
    if _model or not _VOSK_AVAILABLE:
        return _model
    try:
        # Expect a small Vosk model placed in ./backend/models/vosk
        import os
        from pathlib import Path
        model_path = Path(__file__).resolve().parent / 'models' / 'vosk'
        if model_path.exists():
            _model = Model(str(model_path))
        return _model
    except Exception:
        return None

async def transcribe_audio(file: UploadFile) -> str:
    data = await file.read()
    # If Vosk not available or model missing, return a simple fallback notice
    if not _VOSK_AVAILABLE or _load_model() is None:
        return "[transcription unavailable in dev: received %d bytes of audio]" % len(data)
    try:
        # Decode with soundfile
        buf = io.BytesIO(data)
        audio, sr = sf.read(buf, dtype='int16')
        rec = KaldiRecognizer(_model, sr)
        import numpy as np
        if audio.ndim == 2:
            audio = audio.mean(axis=1).astype('int16')
        chunk = audio.tobytes()
        rec.AcceptWaveform(chunk)
        import json
        res = json.loads(rec.Result())
        return res.get('text', '').strip() or '[no speech detected]'
    except Exception:
        return "[transcription failed]"
