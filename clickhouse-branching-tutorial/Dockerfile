FROM python:3.13-slim

WORKDIR /usr/src/app
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

USER 1000
ENTRYPOINT ["python", "app.py"]
