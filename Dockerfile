# =============================================================================
# Ghostfolio Agent Dockerfile
# =============================================================================
# Multi-stage build for optimized image size
#
# Usage:
#   Local development (with docker-compose):
#     docker-compose up --build
#
#   Railway deployment:
#     Backend: Dockerfile.backend (or railway.backend.toml)
#     Frontend: Dockerfile.frontend (or railway.json / railway.frontend.toml)
#
#   Manual run:
#     docker build -t ghostfolio-agent .
#     docker run -p 8000:8000 --env-file .env ghostfolio-agent
# =============================================================================

# -----------------------------------------------------------------------------
# Builder stage
# -----------------------------------------------------------------------------
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# -----------------------------------------------------------------------------
# Production stage
# -----------------------------------------------------------------------------
FROM python:3.11-slim as production

WORKDIR /app

# Install runtime dependencies (including git for repo connect / clone)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set Python environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser
USER appuser

# Copy application code
COPY --chown=appuser:appuser . .

# Railway provides PORT environment variable
# Default to 8000 for local development
ENV PORT=8000

# Expose ports (FastAPI: 8000, Streamlit: 8501)
EXPOSE 8000 8501

# Health check (uses PORT env var for Railway compatibility)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Default command (can be overridden in docker-compose or Railway)
# Uses PORT environment variable for Railway compatibility
CMD uvicorn src.api.app:app --host 0.0.0.0 --port ${PORT:-8000}
