#!/usr/bin/env python3
import boto3
import argparse
import os
from dotenv import load_dotenv

def upload_params_to_ssm(env_file, prefix, region):
    """Upload parameters from .env file to SSM Parameter Store"""
    # Load environment variables from file
    load_dotenv(env_file)
    
    # Initialize SSM client
    ssm_client = boto3.client('ssm', region_name=region)
    
    # Parameters to upload (only override if needed - most are managed by Terraform)
    params = {
        f"{prefix}/mongo-uri": os.environ.get("MONGO_URI", ""),
        f"{prefix}/mongo-db": os.environ.get("MONGO_DB", ""),
    }
    
    # Optional overrides (only include if you need to override Terraform-managed values)
    optional_params = {
        f"{prefix}/aws-region": os.environ.get("AWS_REGION", ""),
        f"{prefix}/mongodb-mcp-server-url": os.environ.get("MONGODB_MCP_SERVER_URL", ""),
        f"{prefix}/mcp-server-url": os.environ.get("MCP_SERVER_URL", ""),
        f"{prefix}/cognito-user-pool-id": os.environ.get("COGNITO_USER_POOL_ID", ""),
        f"{prefix}/cognito-client-id": os.environ.get("COGNITO_CLIENT_ID", ""),
        f"{prefix}/bedrock-agent-id": os.environ.get("BEDROCK_AGENT_ID", ""),
        f"{prefix}/bedrock-agent-alias-id": os.environ.get("BEDROCK_AGENT_ALIAS_ID", "")
    }
    
    # Add optional parameters if they have values
    for key, value in optional_params.items():
        if value:
            params[key] = value
    
    # Upload each parameter
    for name, value in params.items():
        if value:
            print(f"Uploading parameter: {name}")
            ssm_client.put_parameter(
                Name=name,
                Value=value,
                Type='SecureString' if 'uri' in name.lower() else 'String',
                Overwrite=True
            )
        else:
            print(f"Skipping empty parameter: {name}")
    
    print("Parameters uploaded successfully!")
    print("\nNote: Most parameters are automatically managed by Terraform.")
    print("This script should only be used to override specific values if needed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload parameters from .env file to SSM Parameter Store")
    parser.add_argument("--env-file", default=".env", help="Path to .env file")
    parser.add_argument("--prefix", default="/remote-mcp-server", help="SSM parameter name prefix")
    parser.add_argument("--region", default="ap-southeast-2", help="AWS region")
    
    args = parser.parse_args()
    upload_params_to_ssm(args.env_file, args.prefix, args.region)