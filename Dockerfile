# ───────────────────────────────
# 🎛 Discord 통합 관리봇 Dockerfile (Koyeb/Heroku 호환)
# ───────────────────────────────
FROM python:3.11-slim

# ffmpeg 설치
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 작업 디렉토리
WORKDIR /app

# Python 라이브러리 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 코드 복사
COPY discord_clubbot_main.py .
# 선택사항: 쿠키 파일이 있다면 아래 주석 해제
# COPY cookies.txt .

# UTF-8 환경
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8

# 실행
CMD ["python", "discord_clubbot_main.py"]
