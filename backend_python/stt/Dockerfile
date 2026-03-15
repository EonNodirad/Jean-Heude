FROM python:3.10-slim

WORKDIR /app

# 1. Installation des dépendances système indispensables
# ffmpeg : obligatoire pour traiter les fichiers audio
# libgomp1 : obligatoire pour le moteur de calcul ctranslate2 (utilisé par Whisper)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 2. Installation des dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Copie du reste du code
COPY . .

# Pas besoin de memory ici (c'est pour le backend), mais on garde si tu as une logique spécifique
RUN mkdir -p /app/recordings && chmod -R 777 /app/recordings

EXPOSE 8001

CMD ["python", "stt_service.py"]
