FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PYTHONPATH=/app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        gcc \
        g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY mcpuniverse ./mcpuniverse
RUN pip install --upgrade pip \
    && pip install -e ".[dev]"

COPY scripts ./scripts
COPY tests ./tests
COPY .env.example ./

CMD ["python", "-m", "pytest", "tests/benchmark", "tests/evaluator", "tests/mcp"]
