FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2 libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY frontend/dist ./frontend/dist
COPY tests ./tests
COPY run.py README.md ./

# Mount Mindbox.yml.gz.xml and persistent storage/ at runtime:
# docker run -p 8000:8000 -v $(pwd)/Mindbox.yml.gz.xml:/app/Mindbox.yml.gz.xml -v $(pwd)/storage:/app/storage aiforge-softline
EXPOSE 8000

CMD ["python", "run.py", "--host", "0.0.0.0", "--port", "8000"]
