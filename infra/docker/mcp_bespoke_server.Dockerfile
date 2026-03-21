FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY services/mcp_bespoke_server /app
RUN pip install --no-cache-dir -U pip && pip install --no-cache-dir .[dev]

CMD ["python", "-m", "mcp_bespoke_server.server"]

