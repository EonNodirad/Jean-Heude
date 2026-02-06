from kokoro_onnx import Kokoro
import io
import wave
import re
import numpy as np
from fastapi import FastAPI, Body
import asyncio
import uvicorn
from fastapi.responses import StreamingResponse
import time

app = FastAPI(title="Jean-Heude TTS service")
tts_lock = asyncio.Lock()

class TTSService:
    def __init__(self,model_path="model/tts/kokoro-v1.0.onnx",voices_path="model/tts/voices-v1.0.bin"):
        self.kokoro = Kokoro(model_path, voices_path)
        # On choisit une voix par défaut (af_nicole est très claire)
        self.voice = "am_michael"
    
    def generate_wav(self,text:str):
        samples, sample_rate = self.kokoro.create(text, voice = self.voice,speed=1.1, lang="fr-fr")
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file :
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            # Conversion float32 -> int16 pour le format WAV standard
            audio_int16 = (samples * 32767).astype(np.int16)
            wav_file.writeframes(audio_int16.tobytes())
        
        buffer.seek(0)
        return buffer
    async def stream_tts(self, text: str):
        # On découpe le texte par phrases pour générer par petits morceaux
        # On utilise une regex pour garder la ponctuation
        sentences = re.split(r'(?<=[.!?]) +', text)
        
        for sentence in sentences:
            if not sentence.strip(): continue
            
            # On génère le morceau de samples
            # Note: Kokoro est synchrone, on le garde dans un thread pour ne pas bloquer l'event loop
            loop = asyncio.get_running_loop()
            samples, sample_rate = await loop.run_in_executor(None, self.kokoro.create, sentence, self.voice, 1.1, "fr-fr")
            
            # Conversion en int16
            audio_int16 = (samples * 32767).astype(np.int16).tobytes()
            
            # On envoie les octets bruts (sans header WAV pour chaque morceau)
            yield audio_int16

tts = TTSService()
@app.post("/generate")

async def return_audio(payload: dict = Body(...)):
    start_time = time.time()
    text = payload.get("text", "")

    try:
        duration = time.time() - start_time
        print(f"⚡ Synthèse : {duration:.2f}s | Texte : {text[:30]}...")
        return StreamingResponse(
        tts.stream_tts(text), 
        media_type="audio/pcm"
    )
    except Exception as e:
        print(f"❌ Erreur TTS : {e}")
        return {"error": str(e)}
    
    
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
