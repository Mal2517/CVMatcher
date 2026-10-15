FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr && rm -rf /var/lib/apt/lists/*
WORKDIR /code
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Fail the build with a clear message if a file was not uploaded to GitHub
RUN for f in main.py db.py parsing.py scoring.py index.html; do test -f "$f" || (echo "MISSING FILE: $f" && exit 1); done
ENV PORT=8000
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
