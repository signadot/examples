# One image for all three services; the Deployment's `command` picks which runs.
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --uid 1000 --no-create-home app
USER app
EXPOSE 8080
CMD ["uvicorn", "frontend.main:app", "--host", "0.0.0.0", "--port", "8080"]
