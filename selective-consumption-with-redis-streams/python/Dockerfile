FROM python:3.12-slim

WORKDIR /usr/src/app
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY platform_redis ./platform_redis
COPY app ./app
COPY main.py .

USER 1000
ENTRYPOINT ["python", "main.py"]
