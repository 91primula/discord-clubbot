# ───────────────────────────────
# 🎛 Discord 통합 관리봇 Dockerfile
# ───────────────────────────────
FROM python:3.11-slim

# 필수 패키지 설치 (ffmpeg 포함)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 작업 디렉토리 설정
WORKDIR /app

# Python 의존성 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 봇 코드 및 환경파일 복사
COPY discord_clubbot_main.py .
COPY .env .
COPY cookies.txt .  # 선택 사항 (없으면 무시됨)

# UTF-8 환경
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8

# 실행 명령
CMD ["python", "discord_clubbot_main.py"]
