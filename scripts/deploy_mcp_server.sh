#!/bin/bash

# Deploy MCP server to EC2 instance
# Usage: ./deploy_mcp_server.sh <ec2-instance-ip> <ssh-key-path>

EC2_IP=$1
SSH_KEY=$2

if [ -z "$EC2_IP" ] || [ -z "$SSH_KEY" ]; then
    echo "Usage: ./deploy_mcp_server.sh <ec2-instance-ip> <ssh-key-path>"
    exit 1
fi

echo "Packaging MCP server code..."
cd "$(dirname "$0")/.."
tar -czf mcp_server.tar.gz -C src/mcp_server .

echo "Copying files to EC2 instance..."
scp -i "$SSH_KEY" mcp_server.tar.gz ec2-user@"$EC2_IP":~/

echo "Setting up MCP server on EC2 instance..."
ssh -i "$SSH_KEY" ec2-user@"$EC2_IP" << 'EOF'
    sudo yum update -y
    sudo yum install -y docker git python3 python3-pip nodejs npm
    sudo systemctl start docker
    sudo systemctl enable docker
    sudo usermod -a -G docker ec2-user
    
    # Install Node.js 18 (required for MongoDB MCP server)
    curl -fsSL https://rpm.nodesource.com/setup_18.x | sudo -E bash -
    sudo yum install -y nodejs
    
    # Clone the official MongoDB MCP server
    git clone https://github.com/mongodb-js/mongodb-mcp-server.git ~/mongodb-mcp-server
    cd ~/mongodb-mcp-server
    npm install
    
    # Set up our custom MCP server directory
    mkdir -p ~/mcp_server
    tar -xzf ~/mcp_server.tar.gz -C ~/mcp_server
    cd ~/mcp_server
    
    # Install dependencies
    pip3 install -r requirements.txt
    
    # Create systemd service for our custom MCP server
    cat << 'EOT' | sudo tee /etc/systemd/system/custom-mcp-server.service
[Unit]
Description=Custom MCP Server
After=network.target

[Service]
User=ec2-user
WorkingDirectory=/home/ec2-user/mcp_server
ExecStart=/usr/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOT

    # Create systemd service for MongoDB MCP server
    cat << 'EOT' | sudo tee /etc/systemd/system/mongodb-mcp-server.service
[Unit]
Description=MongoDB MCP Server
After=network.target

[Service]
User=ec2-user
WorkingDirectory=/home/ec2-user/mongodb-mcp-server
ExecStart=/usr/bin/node src/server.js --port 8001
Restart=always
RestartSec=10
Environment="MONGODB_URI=mongodb://localhost:27017"

[Install]
WantedBy=multi-user.target
EOT
    
    # Start the services
    sudo systemctl daemon-reload
    sudo systemctl enable custom-mcp-server mongodb-mcp-server
    sudo systemctl start custom-mcp-server mongodb-mcp-server
    
    echo "MCP server deployed and started"
EOF

echo "Cleaning up..."
rm mcp_server.tar.gz

echo "Deployment complete!"