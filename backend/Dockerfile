ARG PYTHON_IMAGE=python:3.12-slim
FROM ${PYTHON_IMAGE} AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/home/interview/.cache/huggingface

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gosu libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 interview

WORKDIR /app

COPY backend/pyproject.toml backend/README.md /tmp/backend/
RUN mkdir -p /tmp/backend/src/interview_agent \
    && touch /tmp/backend/src/interview_agent/__init__.py \
    && python -m pip install --upgrade pip \
    && python -m pip install /tmp/backend \
    && rm -rf /tmp/backend

COPY backend /app/backend
RUN python -m pip install --no-deps /app/backend

COPY knowledge_base /app/knowledge_base
COPY deploy/api-entrypoint.sh /usr/local/bin/interview-api-entrypoint
COPY deploy/backend-entrypoint.sh /usr/local/bin/interview-backend-entrypoint

RUN mkdir -p /app/.interview_agent "$HF_HOME" \
    && chmod +x /usr/local/bin/interview-api-entrypoint /usr/local/bin/interview-backend-entrypoint \
    && chown -R interview:interview /app/.interview_agent /home/interview

EXPOSE 8020

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=8 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8020/health', timeout=4)" || exit 1

ENTRYPOINT ["interview-backend-entrypoint"]
CMD ["interview-api-entrypoint"]

FROM runtime AS embedding

ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu

# Install the CPU wheel first so sentence-transformers cannot resolve a CUDA build.
RUN python -m pip install --index-url "$TORCH_INDEX_URL" "torch>=2.2,<3" \
    && python -m pip install "/app/backend[embeddings]" \
    && chown -R interview:interview /home/interview
