FROM python:3.12-slim
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-noto-core fontconfig \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY LICENSE ./LICENSE
COPY entrypoint.sh ./entrypoint.sh
RUN useradd -r -u 10001 appuser && mkdir -p /app/cache && chown -R appuser:appuser /app && chmod +x /app/entrypoint.sh
EXPOSE 8000
STOPSIGNAL SIGTERM
ENTRYPOINT ["/app/entrypoint.sh"]
