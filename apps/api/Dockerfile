ARG PYTHON_IMAGE=python:3.13.14-slim-bookworm@sha256:9d7f287598e1a5a978c015ee176d8216435aaf335ed69ac3c38dd1bbb10e8d64
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.11.30@sha256:93b61e21202b1dab861092748e46bbd6e0e41dd84f59b9174efd2353186e1b47

FROM ${UV_IMAGE} AS uv

FROM ${PYTHON_IMAGE} AS production-builder
COPY --from=uv /uv /uvx /bin/
WORKDIR /build/apps/api
COPY apps/api/pyproject.toml apps/api/uv.lock ./
COPY apps/api/src ./src
RUN uv sync --frozen --no-dev --no-editable

FROM ${PYTHON_IMAGE} AS migration-builder
COPY --from=uv /uv /uvx /bin/
WORKDIR /build/apps/api
COPY apps/api/pyproject.toml apps/api/uv.lock ./
COPY apps/api/src ./src
RUN uv sync --frozen --no-default-groups --group migration --no-editable

FROM ${PYTHON_IMAGE} AS runtime
ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
RUN groupadd --gid 10001 creativedeploy \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin creativedeploy \
    && mkdir -p /var/lib/creativedeploy/private-images \
    && chown -R 10001:10001 /var/lib/creativedeploy
COPY --from=production-builder /build/apps/api/.venv /opt/venv
WORKDIR /app
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=6 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/live', timeout=2).read()"]
CMD ["python", "-m", "uvicorn", "creativedeploy_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header", "--no-proxy-headers", "--no-access-log"]

FROM ${PYTHON_IMAGE} AS migration
ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
RUN groupadd --gid 10001 creativedeploy \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin creativedeploy
COPY --from=migration-builder /build/apps/api/.venv /opt/venv
WORKDIR /app
COPY --chown=10001:10001 apps/api/alembic.ini ./alembic.ini
COPY --chown=10001:10001 apps/api/migrations ./migrations
USER 10001:10001
ENTRYPOINT ["python", "-m", "alembic", "-c", "/app/alembic.ini"]
CMD ["upgrade", "head"]
