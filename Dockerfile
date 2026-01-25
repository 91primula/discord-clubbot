FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libopus0 \
    libsodium-dev \
    build-essential \
    libffi-dev \
    python3-dev \
    curl \
    ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Deno 설치 (yt-dlp YouTube JS 해석용)
ENV DENO_INSTALL=/root/.deno
ENV PATH=$DENO_INSTALL/bin:$PATH
RUN curl -fsSL https://deno.land/install.sh | sh

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "-u", "discord_clubbot_main.py"]
