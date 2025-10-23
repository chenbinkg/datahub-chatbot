#!/usr/bin/env node

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js';
import { CallToolRequestSchema, ListToolsRequestSchema } from '@modelcontextprotocol/sdk/types.js';
import { S3Client, GetObjectCommand } from '@aws-sdk/client-s3';
import { getSignedUrl } from '@aws-sdk/s3-request-presigner';

// AWS S3 client
const s3Client = new S3Client({
  region: process.env.AWS_REGION || 'ap-southeast-2'
});

// Create MCP server
const server = new Server(
  {
    name: 's3-presigned-url-server',
    version: '1.0.0',
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// Define the generate_presigned_url tool
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: 'generate_presigned_url',
        description: 'Generate presigned URL for S3 dataset download',
        inputSchema: {
          type: 'object',
          properties: {
            bucket: {
              type: 'string',
              description: 'S3 bucket name (default: niwa-data-hub)',
            },
            key: {
              type: 'string',
              description: 'S3 object key/path (e.g., sea-level-change-maps/file.zip)',
            },
            expires_in: {
              type: 'number',
              description: 'URL expiration time in seconds (default: 3600)',
            },
          },
          required: ['key'],
        },
      },
    ],
  };
});

// Handle tool calls
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  if (name === 'generate_presigned_url') {
    try {
      const { 
        bucket = 'niwa-data-hub', 
        key, 
        expires_in = 3600 
      } = args;

      const command = new GetObjectCommand({
        Bucket: bucket,
        Key: key,
      });

      const presignedUrl = await getSignedUrl(s3Client, command, {
        expiresIn: expires_in,
      });

      return {
        content: [
          {
            type: 'text',
            text: `Download URL (expires in ${expires_in} seconds): ${presignedUrl}`,
          },
        ],
      };
    } catch (error) {
      return {
        content: [
          {
            type: 'text',
            text: `Error generating presigned URL: ${error.message}`,
          },
        ],
        isError: true,
      };
    }
  } else {
    throw new Error(`Unknown tool: ${name}`);
  }
});

// Start the server with Streamable HTTP transport
const PORT = process.env.PORT || 8001;
const HOST = process.env.HOST || '0.0.0.0';

const transport = new StreamableHTTPServerTransport({
  port: PORT,
  host: HOST,
});

async function main() {
  await server.connect(transport);
  console.log(`S3 Presigned URL MCP server running on ${HOST}:${PORT}`);
}

main().catch(console.error);