FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

ENV DD_SERVICE=novapay-fraud
ENV DD_ENV=production
ENV DD_VERSION=1.4.0
ENV DD_LOGS_INJECTION=true
ENV DD_TRACE_SAMPLE_RATE=1.0
ENV DD_RUNTIME_METRICS_ENABLED=true
ENV PORT=8003

EXPOSE $PORT

CMD ddtrace-run uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
