# syntax=docker/dockerfile:1.6

# ---- Build 阶段：安装依赖 + 字节码编译 ----
FROM python:3.11-slim-bookworm AS build

# 系统依赖：cryptography 需要 gcc/ffi，ciso8601 需要 build-essential
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libffi-dev libssl-dev curl \
  && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -U pip setuptools wheel poetry==1.8.*

WORKDIR /opt/app

# 仅先复制依赖清单利用层缓存
COPY pyproject.toml poetry.lock* ./
RUN poetry config virtualenvs.create false \
 && poetry install --without dev --no-interaction --no-ansi --no-root || \
    ( [ ! -f poetry.lock ] && poetry lock --no-update && \
      poetry install --without dev --no-interaction --no-ansi --no-root )

# ---- Runtime 阶段：最小镜像，仅保留 runtime 依赖 ----
FROM python:3.11-slim-bookworm AS runtime

# 非 root 用户 + 安全基础
RUN groupadd -r harness && useradd -r -g harness -s /usr/sbin/nologin harness \
 && apt-get update && apt-get install -y --no-install-recommends curl ca-certificates tini \
 && rm -rf /var/lib/apt/lists/*

# 把 build 阶段的 site-packages 和 二进制拷过来
COPY --from=build /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=build /usr/local/bin /usr/local/bin

WORKDIR /opt/app
RUN chown harness:harness /opt/app
USER harness

COPY --chown=harness:harness app ./app
COPY --chown=harness:harness scripts ./scripts 2>/dev/null || true

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENV=prod \
    PYTHONPATH=/opt/app

# API 默认端口，Prometheus 单独端口
EXPOSE 8000 9464

# tini 做 PID 1，处理信号 + 僵尸进程
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips=*", \
     "--workers", "2"]
