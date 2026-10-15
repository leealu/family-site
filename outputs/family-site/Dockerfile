FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    DIARY_DATA_DIR=/app/data

WORKDIR /app
COPY --chown=10001:10001 server.py index.html app.js image-gesture.js style.css admin.css favicon.svg ./
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/state', timeout=3)" || exit 1
CMD ["python", "server.py"]
