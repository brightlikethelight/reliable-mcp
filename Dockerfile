# MCP Reliability Lab - Docker Image

FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs \
    npm \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install MCP filesystem server
RUN npm install -g @modelcontextprotocol/server-filesystem \
    && npm cache clean --force

# Create app directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create test directory
RUN mkdir -p /tmp/mcp-test

# Expose port (for future web UI)
EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV MCP_LAB_TEST_DIR=/tmp/mcp-test

# Default command - run the working demo
CMD ["python", "working_demo.py"]