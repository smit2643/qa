# ---- deps stage ----
FROM python:3.12-slim AS deps
WORKDIR /app
RUN pip install uv
COPY pyproject.toml .
RUN uv pip install --system -e .

# ---- dev stage (used by docker compose for hot reload) ----
FROM deps AS dev
RUN uv pip install --system -e ".[dev]"
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ---- production stage ----
FROM deps AS production
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
