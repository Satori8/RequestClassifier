# Use python:3.11-slim as base
FROM python:3.11-slim

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies using uv (without installing the project itself)
RUN uv sync --frozen --no-install-project --no-dev

# Copy source code and settings
COPY src/ ./src/
COPY settings/ ./settings/
COPY input_requests.csv ./

# Create output directory
RUN mkdir -p output

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Command to run the service
CMD ["python", "-m", "src.main"]
