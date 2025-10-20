FROM python:3.13.7-slim

RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ .
RUN ls -la /app || echo "COPY failed!"
RUN ls -la /app/services/ || echo "services missing!"
EXPOSE 3000

CMD ["uvicorn", "services.auth.auth_main:app", "--host", "0.0.0.0", "--port", "8000"]