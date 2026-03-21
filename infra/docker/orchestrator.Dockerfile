FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY orchestrator /app
RUN pip install --no-cache-dir -U pip && pip install --no-cache-dir .[dev]

CMD ["python", "-m", "orchestrator.api"]

