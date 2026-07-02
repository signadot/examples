FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the platform layer (owned by the platform team)
COPY signadot/ signadot/

# Copy the application code
COPY main.py .
COPY workflows.py .
COPY activities.py .
COPY models.py .
COPY logging_config.py .

EXPOSE 8080

# Command to run the Temporal worker
CMD ["python", "main.py"]