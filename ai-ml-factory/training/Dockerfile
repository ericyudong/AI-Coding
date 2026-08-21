# Training / pipeline worker image (CPU). GPU overlays use CUDA base images in CI matrix.
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY training/ training/
COPY pipelines/ pipelines/
COPY registry/ registry/

ENV PYTHONUNBUFFERED=1
CMD ["python", "training/xgboost/train.py"]
