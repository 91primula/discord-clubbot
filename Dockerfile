# ────────────────────────────────
# Discord ClubBot Dockerfile
# ────────────────────────────────
FROM python:3.11-slim

# 필수 패키지 설치 (ffmpeg 포함)
RUN apt-get update && apt-get install -y ffmpeg && apt-get clean

# 작업 디렉토리
WORKDIR /app

# requirements 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 봇 코드 복사
COPY discord_clubbot_main.py .

# 환경변수 파일 (.env) 포함
COPY .env .

# 실행
CMD ["python", "discord_clubbot_main.py"]
