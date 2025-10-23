# Use Node 20 for MongoDB MCP server compatibility
FROM node:20-alpine

# Create app directory
WORKDIR /app

# Copy package manifest we added (includes mongodb-mcp-server and overrides)
COPY package.json /app/package.json

# Copy S3 MCP server files
COPY s3_presigned_server.js .

# Install dependencies (this will respect "overrides" in package.json)
RUN npm install --no-audit --no-fund

# Create health check (CommonJS)
RUN echo 'const http = require("http"); const server = http.createServer((req, res) => { if (req.url === "/health") { res.writeHead(200); res.end("OK"); } else { res.writeHead(404); res.end("Not Found"); } }); server.listen(8002); console.log("Health check running on port 8002");' > /app/health.cjs

# Create startup script
RUN echo '#!/bin/sh' > /app/start.sh && \
    echo 'set -e' >> /app/start.sh && \
    echo 'echo "=== Starting MCP Servers ==="' >> /app/start.sh && \
    echo 'echo "MongoDB URI: ${MONGO_URI:0:30}..."' >> /app/start.sh && \
    echo '' >> /app/start.sh && \
    echo 'echo "[1/3] Starting MongoDB MCP server on port 8000..."' >> /app/start.sh && \
    echo 'MDB_MCP_CONNECTION_STRING="${MONGO_URI}" MDB_MCP_READ_ONLY=true npx -y mongodb-mcp-server@latest --transport http --httpHost 0.0.0.0 --httpPort 8000 > /tmp/mongodb-mcp.log 2>&1 &' >> /app/start.sh && \
    echo 'MONGODB_PID=$!' >> /app/start.sh && \
    echo 'sleep 3' >> /app/start.sh && \
    echo 'if kill -0 $MONGODB_PID 2>/dev/null; then' >> /app/start.sh && \
    echo '  echo "✓ MongoDB MCP server started (PID: $MONGODB_PID)"' >> /app/start.sh && \
    echo 'else' >> /app/start.sh && \
    echo '  echo "✗ MongoDB MCP server failed to start. Logs:"' >> /app/start.sh && \
    echo '  cat /tmp/mongodb-mcp.log' >> /app/start.sh && \
    echo 'fi' >> /app/start.sh && \
    echo '' >> /app/start.sh && \
    echo 'echo "[2/3] Starting S3 presigned URL MCP server on port 8001..."' >> /app/start.sh && \
    echo 'cd /app && node s3_presigned_server.js > /tmp/s3-mcp.log 2>&1 &' >> /app/start.sh && \
    echo 'S3_PID=$!' >> /app/start.sh && \
    echo 'sleep 2' >> /app/start.sh && \
    echo 'if kill -0 $S3_PID 2>/dev/null; then' >> /app/start.sh && \
    echo '  echo "✓ S3 MCP server started (PID: $S3_PID)"' >> /app/start.sh && \
    echo '  cat /tmp/s3-mcp.log' >> /app/start.sh && \
    echo 'else' >> /app/start.sh && \
    echo '  echo "✗ S3 MCP server failed to start. Logs:"' >> /app/start.sh && \
    echo '  cat /tmp/s3-mcp.log' >> /app/start.sh && \
    echo 'fi' >> /app/start.sh && \
    echo '' >> /app/start.sh && \
    echo 'echo "[3/3] Starting health check on port 8002..."' >> /app/start.sh && \
    echo 'node /app/health.cjs &' >> /app/start.sh && \
    echo 'echo "✓ Health check started"' >> /app/start.sh && \
    echo '' >> /app/start.sh && \
    echo 'echo "=== All servers started. Tailing MongoDB logs ==="' >> /app/start.sh && \
    echo 'tail -f /tmp/mongodb-mcp.log &' >> /app/start.sh && \
    echo 'wait' >> /app/start.sh && \
    chmod +x /app/start.sh

EXPOSE 8000 8001 8002

CMD ["/app/start.sh"]