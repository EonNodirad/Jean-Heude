import io
from fastapi import FastAPI, UploadFile, File
from faster_whisper import WhisperModel
import uvicorn

app = FastAPI(title="Jean-Heude STT service")

MODEL_SIZE = "small"

DEVICE = "cpu"

COMPUTE_TYPE = "int8"

print(f"--- Chargement du modèle Whisper ({MODEL_SIZE}) sur {DEVICE}... ---")

model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
print("--- Modèle STT prêt ! ---")

@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """Reçoit un fichier binaire et renvoie le texte transcrit"""
    try:
        # 1. Lecture du binaire envoyé par ton backend principal
        audio_data = await file.read()
        audio_file = io.BytesIO(audio_data)

        # 2. Transcription
        # beam_size=5 est un standard pour la précision
        segments, info = model.transcribe(audio_file, beam_size=5, language="fr")

        # 3. On rassemble les morceaux de texte
        full_text = " ".join([segment.text for segment in segments]).strip()

        print(f"🎤 Transcription : {full_text}")
        return {"text": full_text, "language": info.language}

    except Exception as e:
        print(f"❌ Erreur STT : {e}")
        return {"error": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
