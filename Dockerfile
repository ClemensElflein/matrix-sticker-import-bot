FROM ubuntu:latest
LABEL authors="Clemens Elflein"

WORKDIR /build

# Install dependencies
RUN apt-get update && \
    apt-get install -y wget tar libwebp-dev librlottie-dev ffmpeg rust-all clang \
    python-is-python3 python3 python3-pip git \
    pkg-config libavutil-dev libavformat-dev libavfilter-dev libavdevice-dev lld nginx && \
    rm -rf /var/lib/apt/lists/*

# Copy repo
COPY ./ /build

WORKDIR /build
# Fetch submodules
RUN git submodule update --init --recursive

# Build and install mstickereditor
RUN cd mstickereditor && cargo install --locked mstickereditor

# Install python dependencies for sticker-bot
RUN cd sticker-bot && pip install --break-system-packages -r requirements.txt

# Copy the web folder to /app/web (this will be hosted for the picker)
RUN mkdir -p /app/web && cp -r stickerpicker/web/. /app/web/

# Copy nginx config
RUN cp -r config/nginx.conf /etc/nginx/conf.d/default.conf

WORKDIR /app
ENTRYPOINT ["bash", "-c", "service nginx start; python /build/sticker-bot/sticker-bot.py"]
