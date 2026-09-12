FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts
COPY data ./data
COPY .env.example ./.env.example

# DEMO_MODE=true by default so the container runs with zero external
# credentials out of the box; override via docker-compose or -e flags.
ENV DEMO_MODE=true \
    DATABASE_URL=sqlite:///./data/environmental_data.db

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
