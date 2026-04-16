FROM python:3.11-slim-bookworm

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Replace default debian repositories with TUNA mirror for faster/stable downloads in China
RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources

# Prevent Python from writing .pyc files, buffer stdout/stderr, and pin common tooling paths
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/root/.local/bin:${PATH}" \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Install system dependencies required by scientific Python stack, Playwright, Streamlit, and WeasyPrint PDF
RUN set -euo pipefail; \
    apt-get update; \
    if apt-cache show libgdk-pixbuf-2.0-0 >/dev/null 2>&1; then \
        GDK_PIXBUF_PKG=libgdk-pixbuf-2.0-0; \
    else \
        GDK_PIXBUF_PKG=libgdk-pixbuf2.0-0; \
    fi; \
    apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        git \
        libgl1 \
        libglib2.0-0 \
        libgtk-3-0 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libpangoft2-1.0-0 \
        "${GDK_PIXBUF_PKG}" \
        libffi-dev \
        libcairo2 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libxcb1 \
        libxcomposite1 \
        libxdamage1 \
        libxext6 \
        libxfixes3 \
        libxi6 \
        libxtst6 \
        libnss3 \
        libxrandr2 \
        libxkbcommon0 \
        libasound2 \
        libx11-xcb1 \
        libxshmfence1 \
        libgbm1 \
        ffmpeg \
        nodejs \
        npm; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Upgrade pip to latest version
RUN pip install --upgrade pip

# Install Python dependencies first to leverage Docker layer caching
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Install Playwright browser binaries (system deps already handled above)
RUN python -m playwright install chromium

# Copy .env
COPY .env.example .env

# Copy application source
COPY . .

# Ensure runtime directories exist even if ignored in build context
RUN mkdir -p /ms-playwright logs final_reports insight_engine_streamlit_reports media_engine_streamlit_reports query_engine_streamlit_reports

EXPOSE 5000

# Default command launches the Flask orchestrator
CMD ["python", "app.py"]
