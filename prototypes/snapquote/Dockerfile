FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app/ ./app/
COPY quotes/ ./quotes/ 2>/dev/null || mkdir -p ./quotes
COPY logos/ ./logos/ 2>/dev/null || mkdir -p ./logos

# Run
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
