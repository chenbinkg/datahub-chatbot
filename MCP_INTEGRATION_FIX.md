# MCP Server Integration Diagnosis & Fix

## Issue Summary

The Strands agent integration with MongoDB and S3 MCP servers over streamable HTTP protocol was failing with:
- **MongoDB MCP Server (port 8000)**: `HTTP 404 Not Found` - Session terminated
- **S3 Presigned URL MCP Server (port 8001)**: `HTTP 400 Bad Request` after initial connection

## Root Causes

### 1. S3 Server Protocol Mismatch ✅ FIXED
**Problem**: The S3 presigned URL server (`s3_presigned_server.js`) was implemented as a simple Express REST API with custom endpoints (`/mcp/tools`, `/mcp/call`), not using the MCP Streamable HTTP protocol.

**Impact**: The client code uses `streamablehttp_client()` which expects the official MCP Streamable HTTP protocol, causing protocol mismatch and 400 errors.

**Fix Applied**: Rewrote `s3_presigned_server.js` to use the `@modelcontextprotocol/sdk` with `StreamableHTTPServerTransport`.

### 2. MongoDB Server Configuration ⚠️ NEEDS VERIFICATION
**Problem**: The MongoDB MCP server is returning 404, which suggests one of:
1. Server not starting properly
2. Missing environment variables
3. MongoDB connection string issues
4. Container health/startup issues

**Current Configuration**:
```bash
MDB_MCP_CONNECTION_STRING="${MONGO_URI}" npx -y mongodb-mcp-server@latest --transport http --httpHost 0.0.0.0 --httpPort 8000
```

## Changes Made

### 1. Updated `s3_presigned_server.js`
- Replaced Express REST API with MCP SDK
- Implemented `StreamableHTTPServerTransport`
- Proper MCP request/response handling
- Maintains same tool functionality (`generate_presigned_url`)
- **Fixed import path**: Use `streamableHttp.js` (camelCase), not `streamable-http.js`

### 2. Updated `s3_package.json`
- Added dependency: `"@modelcontextprotocol/sdk": "^1.20.0"`
- Removed unused: `express`

### 3. Updated `package.json` (main)
- Added MCP SDK v1.20.0 for S3 server
- Kept MongoDB MCP server dependency

### 4. Updated `Dockerfile`
- Fixed S3 server filename reference: `s3_presigned_server.js`
- Added `MDB_MCP_READ_ONLY=true` for MongoDB server security

## Deployment Steps

### 1. Rebuild and Deploy the MCP Server Container

```bash
# Navigate to MCP servers directory
cd /Users/chenb/Documents/GitHub/datahub-chatbot/src/mcp_servers

# Build the Docker image
docker build -t mcp-servers:latest .

# Tag for ECR (replace with your ECR repo URL)
docker tag mcp-servers:latest <ECR_REPO_URL>:latest

# Push to ECR
docker push <ECR_REPO_URL>:latest

# Update ECS service to use new image
aws ecs update-service --cluster <CLUSTER_NAME> --service <SERVICE_NAME> --force-new-deployment
```

### 2. Verify Environment Variables

Ensure the ECS task definition has:
```json
{
  "name": "MONGO_URI",
  "value": "mongodb+srv://username:password@cluster.mongodb.net/database"
}
```

### 3. Check Container Logs

```bash
# Get task ARN
aws ecs list-tasks --cluster <CLUSTER_NAME> --service-name <SERVICE_NAME>

# View logs
aws logs tail /ecs/<LOG_GROUP_NAME> --follow
```

Look for:
- ✅ "Starting MongoDB MCP server on port 8000..."
- ✅ "S3 Presigned URL MCP server running on 0.0.0.0:8001"
- ❌ Any MongoDB connection errors
- ❌ Any npm/package installation errors

## Testing

### Test S3 Server (Port 8001)
```bash
# Test from within the VPC or through ALB
curl -X POST http://<ALB_DNS>:8001 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'
```

Expected: Should return initialization response with protocol negotiation.

### Test MongoDB Server (Port 8000)
```bash
curl -X POST http://<ALB_DNS>:8000 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'
```

Expected: Should return initialization response with MongoDB tools.

## Troubleshooting MongoDB 404 Issue

### Check 1: Container is Running
```bash
aws ecs describe-tasks --cluster <CLUSTER> --tasks <TASK_ARN>
```

### Check 2: Health Check Status
The health check is on port 8002 (`/health` endpoint). Verify it's passing:
```bash
# From within VPC
curl http://<CONTAINER_IP>:8002/health
```

### Check 3: MongoDB Connection
The MongoDB MCP server requires a valid connection string. Test:
```bash
# Get the MONGO_URI from SSM
aws ssm get-parameter --name /datahub-mcp/mongo-uri --with-decryption

# Verify MongoDB is accessible
mongosh "<MONGO_URI>" --eval "db.adminCommand('ping')"
```

### Check 4: Port Binding
Verify the MongoDB MCP server is actually listening on port 8000:
```bash
# Exec into container
aws ecs execute-command --cluster <CLUSTER> --task <TASK_ARN> --container mcp-server-<ENV> --interactive --command "/bin/sh"

# Inside container
netstat -tuln | grep 8000
```

### Check 5: MongoDB MCP Server Logs
Look for specific error messages:
- "Connection refused" → MongoDB URI is wrong or MongoDB is unreachable
- "Authentication failed" → Credentials in MONGO_URI are incorrect
- "Cannot find module" → NPM installation failed

## Known Issues & Solutions

### Issue: ERR_MODULE_NOT_FOUND for streamableHttp
**Symptoms**: `Cannot find module '/app/node_modules/@modelcontextprotocol/sdk/dist/esm/server/streamable-http.js'`
**Root Cause**: Incorrect import path - the file is `streamableHttp.js` (camelCase), not `streamable-http.js` (kebab-case)
**Solution**: 
```javascript
// ❌ Wrong
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamable-http.js';

// ✅ Correct
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js';
```

### Issue: MongoDB MCP Server Not Starting
**Symptoms**: 404 errors, no logs from MongoDB server
**Solutions**:
1. Check `MONGO_URI` environment variable is set correctly
2. Verify MongoDB is accessible from the container (network/security groups)
3. Check if `npx` is downloading the package correctly (might need internet access)
4. Consider using the Docker image directly: `mongodb/mongodb-mcp-server:latest`

### Issue: S3 Server Still Getting 400
**Symptoms**: After fix, still getting 400 errors
**Solutions**:
1. Verify the new image is deployed (check image tag/digest)
2. Clear any ALB/load balancer caching
3. Check CloudWatch logs for JavaScript errors
4. Verify `@modelcontextprotocol/sdk` version compatibility

## Alternative: Use Docker Compose for MongoDB MCP

If the `npx` approach continues to fail, consider using the official Docker image:

Update `Dockerfile`:
```dockerfile
# Instead of npx, use the official image approach or install globally
RUN npm install -g @mongodb-js/mongodb-mcp-server@latest

# Then in startup script:
mongodb-mcp-server --transport http --httpHost 0.0.0.0 --httpPort 8000
```

Or use multi-stage build with the official MongoDB MCP server image.

## Validation Checklist

- [x] S3 server uses MCP Streamable HTTP protocol
- [x] S3 server package.json has MCP SDK dependency
- [x] Dockerfile references correct S3 server filename
- [x] Main package.json includes MCP SDK
- [ ] MongoDB server successfully connects to MongoDB
- [ ] Both servers return 200 on MCP initialize request
- [ ] Strands agent successfully initializes both MCP clients
- [ ] Tools are listed correctly from both servers

## Next Steps

1. **Deploy the updated container** with the S3 server fix
2. **Monitor CloudWatch logs** during startup for both servers
3. **Test the initialize endpoint** for both servers via ALB
4. **Check MongoDB connectivity** if 404 persists
5. **Update MONGO_URI** if connection issues are found
6. **Consider read-only mode** for MongoDB MCP: add `--readOnly` flag

## References

- [MCP Streamable HTTP Protocol](https://github.com/modelcontextprotocol/specification)
- [MongoDB MCP Server](https://github.com/mongodb-labs/mongodb-mcp-server)
- [MCP SDK Documentation](https://github.com/modelcontextprotocol/typescript-sdk)
