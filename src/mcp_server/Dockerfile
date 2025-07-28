FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js for MongoDB MCP server
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs

# Set working directory
WORKDIR /app

# Clone and setup external MongoDB MCP server
RUN git clone https://github.com/mongodb-js/mongodb-mcp-server.git /app/mongodb-mcp
WORKDIR /app/mongodb-mcp
RUN npm install

# Setup main MCP server
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application code
COPY . .

# Expose ports
EXPOSE 8000 8001

# Create startup script
RUN echo '#!/bin/bash\n\
cd /app/mongodb-mcp && node src/server.js --port 8001 &\n\
cd /app && python -m uvicorn main:app --host 0.0.0.0 --port 8000\n\
' > /app/start.sh && chmod +x /app/start.sh

CMD ["/app/start.sh"]