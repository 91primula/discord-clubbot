# ─────────────────────────────────────────────
# 🎛 Discord ClubBot - Dockerfile
# ─────────────────────────────────────────────
FROM python:3.11-slim

# 시스템 패키지 설치 (ffmpeg 포함)
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# 작업 디렉토리 설정
WORKDIR /app

# 필요한 파일 복사
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 봇 코드 및 환경파일 복사
COPY discord_clubbot_main.py .
COPY cookies.txt .

# 실행 명령
CMD ["python", "discord_clubbot_main.py"]
