# Multi-stage build for Construction AI Backend

FROM python:3.11-slim as base

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    wget \
    git \
    autoconf \
    automake \
    libtool \
    make \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Build and install LibreDWG from source
RUN cd /tmp && \
    git clone --depth 1 --branch 0.13.3 https://github.com/LibreDWG/libredwg.git && \
    cd libredwg && \
    sh autogen.sh && \
    ./configure --disable-bindings --disable-doc && \
    make && \
    make install && \
    ldconfig && \
    cd / && \
    rm -rf /tmp/libredwg

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY ./app ./app

# Create upload directory
RUN mkdir -p /app/data/uploads

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]


# Development stage with hot reload
FROM base as development

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]


# Production stage
FROM base as production

# Copy static files if any
# COPY ./static ./static

# Run with production settings
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
