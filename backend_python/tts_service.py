from kokoro_onnx import Kokoro
import io
import wave
import numpy as np

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
