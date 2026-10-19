FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Minimal runtime libraries required by matplotlib (Agg backend) and lxml.
# DejaVu Sans (bundled with matplotlib) provides Cyrillic glyphs for charts.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libfreetype6 \
        libpng16-16 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# SQLite DB and logs live in these volumes (see docker-compose.yml).
RUN mkdir -p /app/data /app/logs

CMD ["python", "-m", "bot.main"]
