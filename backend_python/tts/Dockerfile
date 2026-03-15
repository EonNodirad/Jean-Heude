FROM python:3.10-slim

WORKDIR /app

# 1. On installe wget ET les dépendances système pour l'audio et ONNX
# Libgomp1 est souvent nécessaire pour onnxruntime sur Debian/Ubuntu
RUN apt-get update && apt-get install -y \
    wget \
    libgomp1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 2. On installe les dépendances Python d'abord (meilleure mise en cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Création de l'arborescence
RUN mkdir -p model/tts

# 4. Téléchargement "intelligent"
# Si tu veux vraiment éviter de retélécharger, on peut copier le dossier local d'abord.
# Si le dossier est vide sur ton PC, Docker ne copiera rien, et le script téléchargera.
COPY model* /app/model/

RUN if [ ! -f model/tts/kokoro-v1.0.onnx ]; then \
    echo "📥 Téléchargement du modèle ONNX..." && \
    wget -q https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx -O model/tts/kokoro-v1.0.onnx; \
    fi && \
    if [ ! -f model/tts/voices-v1.0.bin ]; then \
    echo "📥 Téléchargement des voix..." && \
    wget -q https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin -O model/tts/voices-v1.0.bin; \
    fi

# 5. On finit par copier le reste du code
COPY . .

EXPOSE 8002
CMD ["python", "tts_service.py"]
