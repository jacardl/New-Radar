# =============================================================================
# New Radar - Hermes Agent Gateway
# =============================================================================

FROM python:3.11-slim-bookworm

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PYTHONUTF8=1 \
    PYTHONPATH=/app/hermes-agent:/app

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Hermes Agent from local directory
# Use Chinese PyPI mirror for faster download
COPY hermes-agent /app/hermes-agent
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -e /app/hermes-agent[cli,messaging,api_server]

# Copy application files (mcp-servers, skills, microservices)
COPY mcp-servers/ /app/mcp-servers/
COPY skills/ /app/skills/
COPY microservices/ /app/microservices/

# Install MCP server and microservices dependencies
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple \
    "mcp>=1.2.0,<2" \
    "sqlalchemy>=2.0.0,<3" \
    "asyncpg>=0.29.0,<1" \
    "httpx>=0.28.0,<1" \
    "loguru" \
    "pydantic>=2.0.0" \
    "pydantic-settings"

# Create runtime directories
RUN mkdir -p /app/logs /app/final_reports

# Environment variables
ENV HERMES_API_PORT=8642
ENV DB_HOST=db
ENV DB_PORT=5432
ENV DB_USER=radar
ENV DB_PASSWORD=radar
ENV DB_NAME=radar

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8642/health || exit 1

# Default command - run Hermes gateway
CMD ["hermes", "gateway", "run"]
