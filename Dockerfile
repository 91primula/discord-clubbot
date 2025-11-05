# ───────────────────────────────
# Discord ClubBot - Dockerfile
# Koyeb Worker / Docker Compatible
# ───────────────────────────────
FROM python:3.11-slim

# 기본 유틸 설치
RUN apt-get update && \
    apt-get install -y ffmpeg git && \
    rm -rf /var/lib/apt/lists/*

# 작업 폴더
WORKDIR /app

# 패키지 설치
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

# 메인 코드 복사
COPY discord_clubbot_main.py .

# 실행 명령
CMD ["python", "discord_clubbot_main.py"]
