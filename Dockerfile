FROM python:3.11-slim

# ffmpeg 설치
RUN apt-get update && apt-get install -y ffmpeg build-essential --no-install-recommends && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# 환경변수는 Koyeb에서 설정하세요
CMD ["python", "discord_clubbot_main.py"]