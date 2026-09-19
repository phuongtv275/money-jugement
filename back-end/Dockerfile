FROM python:3.11-slim

WORKDIR /app

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install uv from Astral official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy dependency manifests
COPY pyproject.toml uv.lock* ./

# Install dependencies system-wide inside the container
RUN uv pip install --system --no-cache -r pyproject.toml

# Copy source code and mock data
COPY . .

EXPOSE 8000

# Default entrypoint: Run FastAPI mock server
CMD ["python", "mock_server.py"]
