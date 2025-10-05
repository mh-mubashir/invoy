import subprocess
import wave
import json
import os
from vosk import Model, KaldiRecognizer

# Load Vosk model once globally
model = Model("/home/hamza-ubuntu/Documents/Coding/invoy/vosk-model-small-en-us-0.15")

def transcribe_audio(file_path: str) -> str:
    """
    Transcribes an audio file (webm, wav, mp3, etc.) to text using Vosk.
    Converts to 16kHz mono WAV if needed.

    Args:
        file_path: path to the uploaded audio file

    Returns:
        str: transcribed text
    """
    # Ensure .wav format
    print("Transcribing audio file:", file_path)
    wav_path = file_path
    if not file_path.endswith(".wav"):
        wav_path = file_path.rsplit(".", 1)[0] + ".wav"
        subprocess.run([
            "ffmpeg", "-y", "-i", file_path,
            "-ar", "16000", "-ac", "1", "-f", "wav", wav_path
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    wf = wave.open(wav_path, "rb")
    rec = KaldiRecognizer(model, wf.getframerate())

    text = ""
    while True:
        data = wf.readframes(4000)
        if len(data) == 0:
            break
        if rec.AcceptWaveform(data):
            result = json.loads(rec.Result())
            text += result.get("text", "") + " "

    final = json.loads(rec.FinalResult())
    text += final.get("text", "")

    wf.close()

    # Clean up converted wav if needed
    if wav_path != file_path:
        os.remove(wav_path)

    return text.strip()