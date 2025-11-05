# ─────────────────────────────
# 📦 Discord ClubBot Dockerfile
# ─────────────────────────────
FROM python:3.11-slim

# 필수 패키지 설치 (ffmpeg 포함)
RUN apt-get update && apt-get install -y ffmpeg git && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# requirements.txt 먼저 복사 (캐시 활용)
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# 메인 코드 복사
COPY discord_clubbot_main.py .

# 실행 명령
CMD ["python", "discord_clubbot_main.py"]
