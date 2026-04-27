# ─── Image de base légère Python ──────────────────────────────────────────────
FROM python:3.11-slim

# Métadonnées
LABEL maintainer="PFE Master Ingénierie Pédagogique"
LABEL description="Agent Pédagogique Adaptatif pour STI"

# ─── Variables d'environnement ────────────────────────────────────────────────
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# ─── Répertoire de travail ────────────────────────────────────────────────────
WORKDIR /app

# ─── Dépendances système minimales ───────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl espeak espeak-data libespeak1 ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# ─── Dépendances Python ───────────────────────────────────────────────────────
COPY requirements.txt .
COPY requirements-docker.txt .
# En local Docker on utilise requirements-docker.txt (avec pyttsx3)
RUN pip install --no-cache-dir -r requirements-docker.txt

# ─── Copie du code source ─────────────────────────────────────────────────────
COPY . .

# ─── Création du dossier de données (persisté via volume) ────────────────────
RUN mkdir -p /app/data

# ─── Healthcheck ─────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# ─── Port exposé ──────────────────────────────────────────────────────────────
EXPOSE 8501

# ─── Commande de démarrage ────────────────────────────────────────────────────
CMD ["streamlit", "run", "interface.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]
