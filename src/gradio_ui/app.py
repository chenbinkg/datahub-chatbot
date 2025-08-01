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
        chatbot = gr.Chatbot(type="messages")
        msg = gr.Textbox(label="Message")
        mcp_type = gr.Dropdown(
            label="MCP Type",
            choices=[
                "mongodb", 
                "mongodb_external", 
                "aws", 
                "sequential_thinking"
            ],
            value="mongodb"
        )
        clear = gr.Button("Clear")
        
        def respond(message, chat_history, token, mcp_type):
            if not token:
                return chat_history + [{"role": "assistant", "content": "Please login first"}], ""
            
            # Add user message to history
            chat_history.append({"role": "user", "content": message})
            
            # Get response from MCP server via Bedrock agent
            try:
                print(f"Invoking Bedrock Agent - ID: {BEDROCK_AGENT_ID}, Alias: {BEDROCK_AGENT_ALIAS_ID}")
                print(f"Message: {message}, MCP Type: {mcp_type}")
                
                # Send message directly - let agent decide if MCP tools are needed
                enhanced_message = message
                
                # Use a unique session ID to avoid cached agent state
                import uuid
                session_id = f"gradio-{str(uuid.uuid4())[:8]}"
                
                response = bedrock_agent.invoke_agent(
                    agentId=BEDROCK_AGENT_ID,
                    agentAliasId=BEDROCK_AGENT_ALIAS_ID,
                    inputText=enhanced_message,
                    sessionId=session_id,
                    enableTrace=True
                )
                
                print(f"Bedrock agent response keys: {list(response.keys())}")
                
                # Extract response text from Bedrock agent response
                # Bedrock agent returns streaming response, need to read it properly
                result_text = ""
                print(f"Full Bedrock response: {response}")
                
                if 'completion' in response:
                    event_stream = response['completion']
                    try:
                        for event in event_stream:
                            print(f"Processing event: {event}")
                            if 'chunk' in event:
                                chunk = event['chunk']
                                if 'bytes' in chunk:
                                    chunk_text = chunk['bytes'].decode('utf-8')
                                    print(f"Chunk text: {chunk_text}")
                                    result_text += chunk_text
                            elif 'trace' in event:
                                # Check if this trace contains the final response
                                trace = event.get('trace', {})
                                print(f"Trace event: {trace}")
                    except Exception as stream_error:
                        print(f"Error processing stream: {stream_error}")
                        result_text = f"Stream processing error: {str(stream_error)}"
                    
                    result = result_text if result_text else "No response from agent"
                else:
                    result = "No completion in response"
                
                print(f"Final result: {result}")
                
                # Add assistant response to history
                chat_history.append({"role": "assistant", "content": result})
                
            except Exception as e:
                error_msg = f"Error: {str(e)}"
                print(f"Exception occurred: {error_msg}")
                print(f"Exception type: {type(e).__name__}")
                import traceback
                print(f"Traceback: {traceback.format_exc()}")
                chat_history.append({"role": "assistant", "content": error_msg})
            
            return chat_history, ""
        
        msg.submit(respond, [msg, chatbot, token_state, mcp_type], [chatbot, msg])
        clear.click(lambda: None, None, chatbot, queue=False)
        
    login_button.click(
        authenticate,
        [username_input, password_input],
        [login_output, token_state]
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)