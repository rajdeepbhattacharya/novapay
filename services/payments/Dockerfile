FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

ENV DD_SERVICE=novapay-payments
ENV DD_ENV=production
ENV DD_VERSION=2.1.0
ENV DD_LOGS_INJECTION=true
ENV DD_TRACE_SAMPLE_RATE=1.0
ENV DD_RUNTIME_METRICS_ENABLED=true
# Railway provides $PORT dynamically; fall back to 8001 for local/K8s
ENV PORT=8001

EXPOSE $PORT

# Shell form so $PORT is evaluated at runtime
CMD ddtrace-run uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
