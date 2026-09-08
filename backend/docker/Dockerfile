# backend 镜像（交付物之一，主 compose 仅 backend+frontend，不含任何中间件——detail §1.1 部署边界）。
# 参照 offline Dockerfile 惯例：python:3.11-slim、非 root 降权、/healthz 探活、单 worker。
# 锁依赖（requirements.lock / pip-compile）后续补：当前直接 pip install pyproject。
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 先拷包源码与声明再装依赖（利用构建缓存；改动 app 不重装依赖）
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .

# alembic 迁移骨架（启动 command `alembic upgrade head && uvicorn ...`）
COPY alembic ./alembic
COPY alembic.ini ./

# 非 root 降权（收敛「容器 RCE 即 root」风险面，offline P2-E8 同款）
RUN useradd --no-create-home --uid 10001 appuser
USER appuser

EXPOSE 8000

# 无鉴权探活：python slim 无 curl/wget，用标准库 urllib 打 /healthz
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3)"

# 单进程部署约束（detail §1.1）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
