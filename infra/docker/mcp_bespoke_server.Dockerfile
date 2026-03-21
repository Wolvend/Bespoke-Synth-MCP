FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY services/mcp_bespoke_server /app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -U pip && pip install --no-cache-dir ".[dev,audio]"

CMD ["python", "-m", "mcp_bespoke_server.server"]

