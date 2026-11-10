FROM python:3.12-slim AS backend

ARG GIT_COMMIT=unversioned-container
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=10 \
    GIT_COMMIT=${GIT_COMMIT}
WORKDIR /app
RUN apt-get update \
    && apt-get install --no-install-recommends -y libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system app \
    && useradd --system --gid app --home-dir /app app
COPY pyproject.toml README.md ./
RUN mkdir -p src/youbike_forecast \
    && touch src/youbike_forecast/__init__.py
RUN --mount=type=cache,target=/root/.cache/pip pip install ".[models]" \
    && rm -rf src
COPY src ./src
RUN pip install --no-deps . \
    && chown -R app:app /app
USER app
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=3)"]
CMD ["uvicorn", "youbike_forecast.api.main:app", "--host", "0.0.0.0", "--port", "8080"]

