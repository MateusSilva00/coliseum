FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV PYTHONPATH=/app

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen

COPY . .

CMD ["uv", "run", "python", "-m","src.server.init_server"]