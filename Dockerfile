FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install required system dependencies (if any)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      gcc python3-dev build-essential && \
    rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Expose backend port
EXPOSE 8000

# Mount backend .env at runtime
# Command to start the server via run.py (run.py is now mounted)
CMD ["python", "run.py"] 