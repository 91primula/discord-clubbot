FROM python:3.11-slim

# ffmpeg 설치 (유튜브/라디오 오디오 스트림 재생용)
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# 작업 디렉토리 설정
WORKDIR /app

# 파이썬 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 봇 코드 복사
COPY discord_clubbot_main.py .

# (중요) .env는 복사하지 않습니다.
# 실제 토큰/환경변수는 Koyeb의 Environment/Secrets에서 설정하세요.

# 컨테이너 시작 시 실행할 명령
CMD ["python", "discord_clubbot_main.py"]
