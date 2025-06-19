# backend/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
# ENV OPENAI_API_KEY YOUR_API_KEY_HERE # Will be overridden by docker-compose or runtime environment

# Install system dependencies
# For pydub, ffmpeg is often needed. It's good to install it here.
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose the port Uvicorn will run on
EXPOSE 8000

# Run Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
