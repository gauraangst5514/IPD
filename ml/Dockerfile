FROM python:3.11-slim-bookworm
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
COPY ml/requirements.txt /app/ml/requirements.txt
RUN pip install --no-cache-dir -r ml/requirements.txt
COPY ml/ /app/ml/
COPY shared/ /app/shared/
CMD ["uvicorn", "ml.serve:app", "--host", "0.0.0.0", "--port", "8001"]
