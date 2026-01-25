FROM python:3.11-slim

# 환경 변수: 버퍼링 끄기 (로그 바로 보이게)
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# 필수 시스템 패키지:
# - ffmpeg: 오디오 스트리밍
# - libopus0, libsodium-dev: 디스코드 음성/암호화 (PyNaCl용)
# - build-essential, libffi-dev, python3-dev: PyNaCl 빌드용
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libopus0 \
    libsodium-dev \
    build-essential \
    libffi-dev \
    python3-dev \
 && rm -rf /var/lib/apt/lists/*

# 작업 디렉토리
WORKDIR /app

# 파이썬 라이브러리 설치
COPY requirements.txt .
RUN pip install -r requirements.txt

# 봇 코드 복사
COPY . .

# 실행
CMD ["python", "-u", "discord_clubbot_main.py"]
