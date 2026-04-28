# Multi-stage build for its-ok-gemini project
# Stage 1: Build React frontend
FROM node:20-alpine AS frontend-builder

WORKDIR /frontend

# Copy frontend files
COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ .

# Build the React app
RUN npm run build

# Stage 2: Python runtime with FastAPI and frontend
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies (git for GitPython, curl for healthchecks)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    git \
    curl \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd -m -u 1000 appuser
USER appuser

# Copy Python requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser migrations/ ./migrations/
COPY --chown=appuser:appuser alembic.ini .

# Copy built frontend from stage 1
COPY --chown=appuser:appuser --from=frontend-builder /frontend/dist ./frontend/dist

# Create a simple FastAPI app to serve static files
RUN mkdir -p /app/static && \
    if [ -d /app/frontend/dist ]; then cp -r /app/frontend/dist/* /app/static/ 2>/dev/null || true; fi

# Expose port
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the FastAPI application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]