import io
from fastapi import FastAPI, UploadFile, File, Form
from faster_whisper import WhisperModel
import uvicorn

app = FastAPI(title="Jean-Heude STT service")

MODEL_SIZE = "small"
DEVICE = "cpu"
COMPUTE_TYPE = "int8"

print(f"--- Chargement du modèle Whisper ({MODEL_SIZE}) sur {DEVICE}... ---")
model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
print("--- Modèle STT prêt ! ---")

def format_timestamp(seconds: float, is_end=False) -> str:
    """Convertit des secondes en format temporel SRT, avec un écart d'1ms pour la fin"""
    if is_end:
        seconds = max(0.0, seconds - 0.001) # Retire 1 milliseconde pour DaVinci
        
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """Reçoit un fichier binaire et renvoie le texte transcrit brut"""
    try:
        audio_data = await file.read()
        audio_file = io.BytesIO(audio_data)

        segments, info = model.transcribe(audio_file, beam_size=5, language="fr")
        full_text = " ".join([segment.text for segment in segments]).strip()

        print(f"🎤 Transcription brute : {full_text}")
        return {"text": full_text, "language": info.language}

    except Exception as e:
        print(f"❌ Erreur STT : {e}")
        return {"error": str(e)}

@app.post("/subtitles")
async def generate_subtitles(
    file: UploadFile = File(...),
    max_chars: int = Form(30)  # 30 par défaut si on n'envoie rien
):
    """Reçoit un fichier et renvoie les sous-titres découpés selon max_chars"""
    try:
        audio_data = await file.read()
        audio_file = io.BytesIO(audio_data)

        # L'ASTUCE EST ICI : word_timestamps=True
        segments, info = model.transcribe(audio_file, beam_size=5, language="fr", word_timestamps=True)

        srt_content = ""
        json_segments = []
        subtitle_index = 1

        for segment in segments:
            # Sécurité au cas où Whisper ne trouve pas de mots dans ce segment
            if not segment.words:
                continue

            current_text = ""
            start_time = segment.words[0].start
            end_time = segment.words[0].end

            for word_obj in segment.words:
                word_str = word_obj.word.strip()

                # Si c'est le premier mot du bloc
                if not current_text:
                    current_text = word_str
                    start_time = word_obj.start
                    end_time = word_obj.end
                # Si ajouter le nouveau mot dépasse la limite
                elif len(current_text) + 1 + len(word_str) > max_chars:
                    # 1. On sauvegarde le bloc actuel
                    srt_content += f"{subtitle_index}\n"
                    srt_content += f"{format_timestamp(start_time)} --> {format_timestamp(end_time)}\n"
                    srt_content += f"{current_text}\n\n"
                    
                    json_segments.append({"id": subtitle_index, "start": start_time, "end": end_time, "text": current_text})
                    subtitle_index += 1
                    
                    # 2. On commence un nouveau bloc avec ce mot
                    current_text = word_str
                    start_time = word_obj.start
                    end_time = word_obj.end
                else:
                    # Le mot rentre, on l'ajoute et on repousse la fin du chrono
                    current_text += " " + word_str
                    end_time = word_obj.end

            # Ne pas oublier de sauvegarder le dernier morceau du segment !
            if current_text:
                srt_content += f"{subtitle_index}\n"
                srt_content += f"{format_timestamp(start_time)} --> {format_timestamp(end_time, is_end=True)}\n"
                srt_content += f"{current_text}\n\n"
                
                json_segments.append({"id": subtitle_index, "start": start_time, "end": end_time, "text": current_text})
                subtitle_index += 1

        print(f"🎬 Sous-titres (max {max_chars} chars) générés avec succès !")
        return {"language": info.language, "srt": srt_content, "segments": json_segments}

    except Exception as e:
        print(f"❌ Erreur : {e}")
        return {"error": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)