FROM python:3.10-slim

WORKDIR /app

# 1. Installation de Node.js + Dépendances pour Puppeteer (Chrome headless)
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    libnss3 \
    libatk-bridge2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpangocairo-1.0-0 \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# 2. Installation des dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Copie de l'intégralité du code (incluant tes dossiers MCP)
COPY . .

# 4. Installation des dépendances Node pour chaque MCP
# On boucle sur tes dossiers pour faire un 'npm install' là où c'est nécessaire
RUN cd mcp_servers_prive/meteo_mcp && npm install || true
RUN cd mcp_servers_prive/puppeteer_mcp && npm install || true
RUN cd mcp_servers_prive/world_monitor_mcp && npm install || true

# 5. Permissions et Dossiers
RUN mkdir -p /app/memory/uploads /app/memory/users /app/skills
RUN chmod -R 777 /app/memory /app/skills

RUN chmod +x /app/start.sh

EXPOSE 8000

CMD ["/app/start.sh"]