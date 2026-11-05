ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.12.1
FROM ${UV_IMAGE} AS uv

FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLBACKEND=Agg \
    PYTHONPATH=/opt/coinjoin-analysis/src \
    UV_NO_CACHE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/usr/local

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        build-essential \
        ca-certificates \
        curl \
        fontconfig \
        fonts-dejavu-core \
        git \
        graphviz \
        libgmp-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/coinjoin-analysis

COPY --from=uv /uv /uvx /bin/

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --inexact --no-install-project

COPY . .
RUN uv sync --locked --no-dev --inexact \
    && chmod +x /opt/coinjoin-analysis/docker/analysis-entrypoint.sh

ENTRYPOINT ["/opt/coinjoin-analysis/docker/analysis-entrypoint.sh"]
CMD ["help"]
