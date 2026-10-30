FROM python:3.11-slim

WORKDIR /app

# Install system deps for OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY ml/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir timm

# Copy ML code (weights are mounted as volume)
COPY ml/ ./ml/

EXPOSE 8001

CMD ["uvicorn", "ml.serve:app", "--host", "0.0.0.0", "--port", "8001"]
