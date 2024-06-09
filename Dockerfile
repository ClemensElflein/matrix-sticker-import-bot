FROM python:3.12-slim-bullseye as base
LABEL authors="Clemens Elflein"

WORKDIR /build

# Install dependencies
RUN apt-get update && \
    apt-get install --no-install-recommends -y libwebp-dev librlottie-dev ffmpeg \
    libavutil-dev libavformat-dev libavfilter-dev libavdevice-dev nginx && \
    rm -rf /var/lib/apt/lists/*

# Install pip requirements.txt
COPY ./sticker-bot/requirements.txt .
RUN pip install -r requirements.txt && rm requirements.txt

FROM base as build

# Install build  dependencies
RUN apt-get update && \
    apt-get install -y clang git \
    pkg-config lld curl && \
    rm -rf /var/lib/apt/lists/*

# Install Rust
# Get Rust
RUN curl https://sh.rustup.rs -sSf | bash -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

COPY ./ /build

WORKDIR /build

# Build and install mstickereditor
RUN cd mstickereditor && cargo build --locked --release

FROM base as runtime

# Copy the mstickereditor binary
COPY --from=build /build/mstickereditor/target/release/mstickereditor /root/.cargo/bin/mstickereditor
COPY --from=build /build/stickerpicker/web /app/web
COPY --from=build /build/config/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /build/sticker-bot /app/sticker-bot

WORKDIR /app
ENTRYPOINT ["bash", "-c", "service nginx start; python /app/sticker-bot/sticker-bot.py"]
