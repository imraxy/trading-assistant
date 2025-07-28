# Multi-stage Docker build for AI Trading Assistant

# Stage 1: Build dependencies including TA-Lib
FROM python:3.11-slim as builder

# Install system dependencies for TA-Lib compilation
RUN apt-get update && apt-get install -y \
    build-essential \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Download and install TA-Lib C library
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz && \
    tar -xzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib/ && \
    ./configure --prefix=/usr && \
    make && \
    make install && \
    cd .. && \
    rm -rf ta-lib ta-lib-0.4.0-src.tar.gz

# Create virtual environment and install Python dependencies
COPY requirements.txt /tmp/requirements.txt
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --upgrade pip && \
    pip install wheel && \
    pip install -r /tmp/requirements.txt

# Stage 2: Production image
FROM python:3.11-slim as production

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libta-lib0 \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root user
RUN groupadd -r trading && useradd -r -g trading trading

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=trading:trading . .

# Create logs directory
RUN mkdir -p /app/logs && chown trading:trading /app/logs

# Switch to non-root user
USER trading

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"] 