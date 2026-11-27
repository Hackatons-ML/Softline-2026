FROM node:22-alpine AS frontend-builder

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend ./
RUN npm run build


FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2 libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY Mindbox.yml.gz run.py README.md ./
COPY backend ./backend
COPY tests ./tests
COPY --from=frontend-builder /frontend/dist ./frontend/dist

# Pre-build SQLite, BM25F, and ONNX embeddings inside the image
RUN python -m backend.data.build_index

ENV HF_HUB_OFFLINE=1
EXPOSE 8000

CMD ["python", "run.py", "--host", "0.0.0.0", "--port", "8000"]
