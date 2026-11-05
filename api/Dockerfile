FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

FROM base AS builder
COPY pyproject.toml ./
RUN pip install --no-cache-dir --prefix=/install .

FROM base AS runtime
COPY --from=builder /install /usr/local
COPY . .
RUN useradd -m -u 1000 pokelab && chown -R pokelab:pokelab /app
USER pokelab
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
