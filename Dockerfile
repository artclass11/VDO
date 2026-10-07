FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -r requirements.txt piper-tts

ENV VDO_OUTPUT_DIR=/data/outputs
VOLUME ["/data"]
ENTRYPOINT ["python", "main.py"]
