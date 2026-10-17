# Citra untuk Cloud Run: API FastAPI dan, dengan perintah berbeda, tugas siklus per jam.
# Versi Python disamakan dengan lingkungan yang sudah diuji (.venv lokal, 3.13).
FROM python:3.13-slim

# libgomp1 dibutuhkan XGBoost (OpenMP); citra slim tidak menyertakannya.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Pustaka dipasang sebelum kode disalin, agar lapisan ini tersimpan di cache
# selama requirements.txt tidak berubah.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Berkas model portabel (10 x Gxx_bundel.joblib + Gxx_xgb.ubj), disalin ke folder
# proyek lebih dulu; lihat panduan deploy.
COPY model_portabel/ ./model_portabel/

COPY *.py ./
COPY api/ ./api/

ENV FOLDER_MODEL=/app/model_portabel

# Cloud Run mengisi PORT; bawaan 8080.
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
