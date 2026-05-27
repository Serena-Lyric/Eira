FROM python:3.11-slim AS builder
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev || uv sync --no-dev

FROM python:3.11-slim AS runtime
RUN useradd -u 10001 -m eira
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --chown=eira:eira . .
ENV PATH=/app/.venv/bin:$PATH
USER eira
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
