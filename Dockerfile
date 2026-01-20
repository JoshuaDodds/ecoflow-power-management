FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (if needed for future extensions)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY __version__.py .
COPY main.py .
COPY services/ ./services/
COPY agents/ ./agents/
COPY utils/ ./utils/
COPY tools/ ./tools/

# Create a non-root user for security
RUN useradd -m -u 1000 ecoflow && \
    chown -R ecoflow:ecoflow /app

USER ecoflow

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Health check (optional - checks if main process is running)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD pgrep -f "python.*main.py" || exit 1

# Run the orchestrator
ENTRYPOINT ["python3", "-u", "main.py"]
