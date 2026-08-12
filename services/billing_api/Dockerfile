FROM python:3.12-slim

WORKDIR /app

COPY services/billing_api/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY . /app

ENV PYTHONUNBUFFERED=1

CMD ["sh", "-c", "uvicorn services.billing_api.app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
