# Production Dockerfile for Azure Container App
# Build context should be the project root
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy project root files (pyproject.toml)
COPY pyproject.toml ./

# Copy geodesic package (required before editable install)
COPY geodesic ./geodesic/

# Copy requirements file from app directory
COPY app/requirements.txt ./app/

# Install Python dependencies
# First install the geodesic package with optional dependencies
RUN pip install --no-cache-dir -e .[agents,calculator] && \
    pip install --no-cache-dir -r app/requirements.txt

# Copy application code
# Copy app directory (excluding files in .dockerignore)
COPY app ./app/

# Set working directory to app
WORKDIR /app/app

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose health check port
EXPOSE 8080

# Run the application
CMD ["python", "main.py"]


