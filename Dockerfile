# Minimal production Dockerfile with Gunicorn (no TLS termination here)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
COPY src /app/src

# Non-root user (optional hardening)
RUN useradd -m appuser
USER appuser

ENV LPS2_PORT=5000
EXPOSE 5000

# Run via Gunicorn (Flask app object in src/app.py is named 'app')
CMD ["gunicorn", "-b", "0.0.0.0:5000", "src.app:app"]
