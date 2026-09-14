FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY LICENSE ./LICENSE
RUN useradd -r -u 10001 appuser && mkdir -p /app/cache && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
STOPSIGNAL SIGTERM
CMD ["sh","-c","exec uvicorn app.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8000} --workers 1"]
