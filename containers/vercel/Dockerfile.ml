FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
# Vercel provides CPU inference. Avoid installing several GB of unused CUDA libraries.
RUN pip install --no-cache-dir torch==2.3.0+cpu torchvision==0.18.0+cpu --index-url https://download.pytorch.org/whl/cpu
COPY ml/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
ENV PYTHONPATH=/app HF_HUB_DISABLE_XET=1 YOLO_CONFIG_DIR=/tmp/yolo MPLCONFIGDIR=/tmp/matplotlib RETRIEVAL_GALLERY=/tmp/retrieval-gallery OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
COPY ml/safe_checkpoint.py ./ml/safe_checkpoint.py
COPY scripts/provision_evidence_models.py ./scripts/provision_evidence_models.py
# Provisioned models are cached independently of normal source-code edits.
RUN python scripts/provision_evidence_models.py
COPY ml/ ./ml/
EXPOSE 80
CMD ["uvicorn", "ml.serve:app", "--host", "0.0.0.0", "--port", "80"]
