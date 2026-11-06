FROM python:3.11-slim

# CPU torch by default; compose.gpu.yaml overrides TORCH_INDEX with a CUDA index.
ARG TORCH_INDEX=https://download.pytorch.org/whl/cpu
ARG MODEL=yolov8s.pt

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN pip install --no-cache-dir torch==2.5.1 torchvision==0.20.1 --index-url ${TORCH_INDEX}
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Bake weights at build time so runtime is fully offline.
WORKDIR /opt/weights
RUN python -c "from ultralytics import YOLO; YOLO('${MODEL}')"
WORKDIR /app

COPY . .

ENV DATA_DIR=/data \
    TRAFFIC_MODEL=/opt/weights/${MODEL} \
    TRAFFIC_DEVICE=cpu \
    TRAFFIC_TRACKER=bytetrack \
    YOLO_AUTOINSTALL=false \
    PYTHONUNBUFFERED=1
VOLUME /data
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8080/api/health',timeout=4)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
