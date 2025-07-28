import os
import json
import boto3
import gradio as gr
import requests
from auth import verify_token, get_token

# Function to get parameters from SSM
def get_ssm_parameter(name, default_value=None):
    try:
        ssm_client = boto3.client('ssm', region_name=os.environ.get('AWS_REGION', 'ap-southeast-2'))
        response = ssm_client.get_parameter(Name=name, WithDecryption=True)
        return response['Parameter']['Value']
    except Exception as e:
        print(f"Error getting SSM parameter {name}: {str(e)}")
        return default_value

# Get configuration from SSM Parameter Store
AWS_REGION = get_ssm_parameter('/remote-mcp-server/aws-region', 'ap-southeast-2')
MCP_SERVER_URL = get_ssm_parameter('/remote-mcp-server/mcp-server-url', 'http://localhost:8000')
MONGODB_MCP_SERVER_URL = get_ssm_parameter('/remote-mcp-server/mongodb-mcp-server-url', 'http://localhost:8001')
COGNITO_USER_POOL_ID = get_ssm_parameter('/remote-mcp-server/cognito-user-pool-id')
COGNITO_CLIENT_ID = get_ssm_parameter('/remote-mcp-server/cognito-client-id')
BEDROCK_AGENT_ID = get_ssm_parameter('/remote-mcp-server/bedrock-agent-id')
BEDROCK_AGENT_ALIAS_ID = get_ssm_parameter('/remote-mcp-server/bedrock-agent-alias-id')

# Initialize Bedrock client
bedrock_runtime = boto3.client(
    service_name="bedrock-runtime",
    region_name=AWS_REGION
)

# Initialize Bedrock agent client
bedrock_agent = boto3.client(
    service_name="bedrock-agent-runtime",
    region_name=AWS_REGION
)

def authenticate(username, password):
    """Authenticate user with Cognito"""
    try:
        token = get_token(username, password, COGNITO_CLIENT_ID)
        return True, token
    except Exception as e:
        return False, str(e)

def process_query(query, token, mcp_type="mongodb_external", history=None):
    """Process user query through Bedrock agent and MCP server"""
    if not verify_token(token, COGNITO_USER_POOL_ID):
        return "Authentication failed. Please log in again."
    
    if history is None:
        history = []
    
    try:
        # Call Bedrock agent with the query
        response = bedrock_agent.invoke_agent(
            agentId=BEDROCK_AGENT_ID,
            agentAliasId=BEDROCK_AGENT_ALIAS_ID,
            inputText=query,
            sessionId="gradio-session",  # You might want to make this user-specific
            enableTrace=True,
            sessionState={
                "mcp_type": mcp_type  # Pass the MCP type to the agent
            }
        )
        
        # Extract the response
        result = json.loads(response["completion"])
        
        # Update conversation history
        history.append((query, result))
        
        return history
    except Exception as e:
        return f"Error: {str(e)}"

# Create Gradio interface
with gr.Blocks(title="Data Platform Chatbot") as demo:
    gr.Markdown("# Data Platform Chatbot")
    gr.Markdown("Connect with MongoDB through our MCP server")
    
    with gr.Tab("Login"):
        username_input = gr.Textbox(label="Username")
        password_input = gr.Textbox(label="Password", type="password")
        login_button = gr.Button("Login")
        login_output = gr.Textbox(label="Status")
        token_state = gr.State("")
        
    with gr.Tab("Chat"):
        chatbot = gr.Chatbot()
        msg = gr.Textbox(label="Message")
        mcp_type = gr.Dropdown(
            label="MCP Type",
            choices=[
                "mongodb", 
                "mongodb_external", 
                "aws", 
                "sequential_thinking"
            ],
            value="mongodb_external"
        )
        clear = gr.Button("Clear")
        
        def respond(message, chat_history, token, mcp_type):
            if not token:
                return chat_history + [("", "Please login first")]
            
            updated_history = process_query(message, token, mcp_type, chat_history)
            return updated_history, ""
        
        msg.submit(respond, [msg, chatbot, token_state, mcp_type], [chatbot, msg])
        clear.click(lambda: None, None, chatbot, queue=False)
        
    login_button.click(
        authenticate,
        [username_input, password_input],
        [login_output, token_state]
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)