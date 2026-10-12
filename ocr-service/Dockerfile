# =========================================================================
# SM-Park - Service OCR (FastAPI + EasyOCR + OpenCV, CPU)
# =========================================================================
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Dépendances système requises par OpenCV/scikit-image/torch
RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libgomp1 \
        libsm6 \
        libxext6 \
        libxrender1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1) PyTorch CPU only (évite les wheels CUDA volumineuses)
RUN pip install --no-cache-dir \
        torch==2.2.2 torchvision==0.17.2 \
        --index-url https://download.pytorch.org/whl/cpu

# 2) Reste des dépendances
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3) Pré-téléchargement des modèles EasyOCR (image autonome / hors-ligne)
RUN python -c "import easyocr; easyocr.Reader(['en'], gpu=False, verbose=False)"

COPY app ./app

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
