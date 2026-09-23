FROM python:3.11-slim

WORKDIR /app

# Install dependencies
# 部署机访问官方 PyPI 较慢且元数据解析易失败，默认走清华镜像；需要官方源可 build-arg 覆盖
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG PIP_DEFAULT_TIMEOUT=120
ARG PIP_RETRIES=10
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY run.py .

# Create data directory for persistent storage
RUN mkdir -p data

# Expose the default port
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/front-login', timeout=4)" || exit 1

# Must bind to 0.0.0.0 inside container so external requests can reach the app
ENV APP_HOST=0.0.0.0

# Production server: MUST stay single-worker (background schedulers and caches
# live in-process); threads handle concurrent HTTP requests.
CMD ["gunicorn", "--workers", "1", "--threads", "8", "--bind", "0.0.0.0:8080", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "run:app"]
