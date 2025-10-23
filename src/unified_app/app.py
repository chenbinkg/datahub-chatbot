import os
import json
import boto3
import gradio as gr
import asyncio
import logging
from auth import verify_token, get_token
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Function to get parameters from SSM
def get_ssm_parameter(name, default_value=None):
    try:
        ssm_client = boto3.client('ssm', region_name=os.environ.get('AWS_REGION', 'ap-southeast-2'))
        response = ssm_client.get_parameter(Name=name, WithDecryption=True)
        return response['Parameter']['Value']
    except Exception as e:
        logger.error(f"Error getting SSM parameter {name}: {str(e)}")
        return default_value

# Get configuration from SSM Parameter Store
AWS_REGION = get_ssm_parameter('/datahub-mcp/aws-region', 'ap-southeast-2')
COGNITO_CLIENT_ID = get_ssm_parameter('/datahub-mcp/cognito-client-id')
MONGO_URI = get_ssm_parameter('/datahub-mcp/mongo-uri')
MONGO_DB = get_ssm_parameter('/datahub-mcp/mongo-db', 'metadata')

# Create BedrockModel
bedrock_model = BedrockModel(
    model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
    region_name="ap-southeast-2",
    temperature=0.3,
)

# Get ALB DNS name from SSM
ALB_DNS_NAME = get_ssm_parameter('/datahub-mcp/alb-dns-name', 'localhost')

# MCP client instances (initialized lazily)
mongodb_mcp_client = None
s3_presigned_mcp_client = None

def get_mongodb_mcp_client():
    global mongodb_mcp_client
    if mongodb_mcp_client is None:
        mongodb_mcp_client = MCPClient(lambda: streamablehttp_client(f"http://{ALB_DNS_NAME}:8000/mcp"))
    return mongodb_mcp_client

def get_s3_presigned_mcp_client():
    global s3_presigned_mcp_client
    if s3_presigned_mcp_client is None:
        s3_presigned_mcp_client = MCPClient(lambda: streamablehttp_client(f"http://{ALB_DNS_NAME}:8001"))
    return s3_presigned_mcp_client

# Load system prompt from agent instruction file
def load_system_prompt():
    try:
        with open('/app/agent_instruction.txt', 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return "You are a helpful AI assistant for DataHub data search, retrieval, and presigned URL generation."

# Initialize agent with MCP tools (lazy initialization)
def initialize_agent():
    tools = []
    
    # Collect tools from all MCP servers
    try:
        client = get_mongodb_mcp_client()
        with client:
            tools.extend(client.list_tools_sync())
    except Exception as e:
        logger.error(f"MongoDB MCP server not available: {e}")
    
    # try:
    #     client = get_s3_presigned_mcp_client()
    #     with client:
    #         tools.extend(client.list_tools_sync())
    # except Exception as e:
    #     logger.error(f"S3 presigned URL MCP server not available: {e}")
    
    system_prompt = load_system_prompt()
    return Agent(model=bedrock_model, tools=tools, system_prompt=system_prompt, callback_handler=None)

# Initialize agent without MCP tools initially (will be reinitialized when needed)
agent = Agent(model=bedrock_model, tools=[], system_prompt=load_system_prompt(), callback_handler=None)

def authenticate(username, password):
    """Authenticate user with Cognito"""
    try:
        token = get_token(username, password, COGNITO_CLIENT_ID)
        return True, token
    except Exception as e:
        return False, str(e)



# Create Gradio interface
with gr.Blocks(title="Datahub Chatbot") as demo:
    gr.Markdown("#Datahub Chatbot")
    gr.Markdown("Connect with Datahub through our MCP server")
    
    with gr.Tab("Login"):
        username_input = gr.Textbox(label="Username")
        password_input = gr.Textbox(label="Password", type="password")
        login_button = gr.Button("Login")
        login_output = gr.Textbox(label="Status")
        token_state = gr.State("")
        
    with gr.Tab("Chat"):
        chatbot = gr.Chatbot(type="messages", height=600)
        msg = gr.Textbox(label="Message")
        verbose_mode = gr.Checkbox(label="Show Reasoning", value=False)
        clear = gr.Button("Clear")
        
        async def respond_async(message, chat_history, token, verbose):
            if not token:
                yield chat_history + [{"role": "assistant", "content": "Please login first"}], ""
                return
            
            # Add user message to history
            chat_history.append({"role": "user", "content": message})
            
            try:
                # Reinitialize agent with MCP tools if needed
                global agent
                if not agent.tool_names:
                    agent = initialize_agent()
                
                # Keep MCP client session alive during agent execution
                mcp_client = get_mongodb_mcp_client()
                with mcp_client:
                    # Process query using Strands Agent streaming
                    result_text = ""
                    reasoning_info = []
                    tool_info = []
                    lifecycle_info = []
                    current_tools = {}  # Track tool inputs to log only when complete
                    
                    agent_stream = agent.stream_async(message)
                    async for event in agent_stream:
                        # Lifecycle events
                        if event.get("init_event_loop"):
                            lifecycle_info.append("🔄 Event loop initialized")
                            logger.info("Event loop initialized")
                        elif event.get("start_event_loop"):
                            lifecycle_info.append("▶️ Event loop cycle starting")
                            logger.info("Event loop cycle starting")
                        elif "message" in event:
                            logger.info(f"New message created: {event['message']['role']}")
                        elif event.get("force_stop"):
                            reason = event.get("force_stop_reason", "unknown")
                            lifecycle_info.append(f"🛑 Force stopped: {reason}")
                            logger.warning(f"Event loop force-stopped: {reason}")
                        
                        # Text generation - stream to UI
                        if "data" in event:
                            result_text += event["data"]
                            # Update chat history in real-time for streaming effect
                            if chat_history and chat_history[-1]["role"] == "assistant":
                                chat_history[-1]["content"] = result_text
                            else:
                                chat_history.append({"role": "assistant", "content": result_text})
                            yield chat_history, ""
                        
                        # Tool events - only log complete tool input
                        if "current_tool_use" in event:
                            tool_use = event["current_tool_use"]
                            if tool_use.get("name"):
                                tool_id = tool_use.get("toolUseId", tool_use["name"])
                                tool_name = tool_use["name"]
                                tool_input = tool_use.get("input", {})
                                
                                # Store current tool state
                                current_tools[tool_id] = {"name": tool_name, "input": tool_input}
                                
                                # Only log if input appears complete (has closing brace)
                                input_str = str(tool_input)
                                if tool_input and (isinstance(tool_input, dict) or input_str.endswith("}")):
                                    if tool_id not in [t.split(":")[0] for t in tool_info if ":" in t]:
                                        tool_info.append(f"🔧 Tool: {tool_name}")
                                        logger.info(f"Using tool: {tool_name} with input: {tool_input}")
                        
                        if "tool_stream_event" in event:
                            tool_data = event["tool_stream_event"].get("data", "")
                            if tool_data:
                                logger.info(f"Tool stream data: {tool_data[:100]}...")  # Truncate long data
                        
                        # Reasoning events
                        if event.get("reasoning"):
                            reasoning_text = event.get("reasoningText", "")
                            if reasoning_text:
                                reasoning_info.append(f"🧠 Reasoning: {reasoning_text}")
                                logger.info(f"Reasoning: {reasoning_text}")
                        
                        if "redactedContent" in event:
                            logger.info("Reasoning content was redacted by model")
                    
                    # Build verbose output if enabled
                    if verbose:
                        verbose_parts = []
                        if lifecycle_info:
                            verbose_parts.append("**Lifecycle:**\n" + "\n".join(lifecycle_info))
                        if tool_info:
                            verbose_parts.append("**Tools Used:**\n" + "\n".join(tool_info))
                        if reasoning_info:
                            verbose_parts.append("**Reasoning:**\n" + "\n".join(reasoning_info))
                        
                        if verbose_parts:
                            result_text = "\n\n".join(verbose_parts) + "\n\n---\n\n" + result_text
                    
                    # Update final response
                    if chat_history and chat_history[-1]["role"] == "assistant":
                        chat_history[-1]["content"] = result_text
                    else:
                        chat_history.append({"role": "assistant", "content": result_text})
                
            except Exception as e:
                error_msg = f"Error: {str(e)}"
                chat_history.append({"role": "assistant", "content": error_msg})
                yield chat_history, ""
            
            yield chat_history, ""
        
        msg.submit(respond_async, [msg, chatbot, token_state, verbose_mode], [chatbot, msg])
        clear.click(lambda: None, None, chatbot, queue=False)
        
    login_button.click(
        authenticate,
        [username_input, password_input],
        [login_output, token_state]
    )

if __name__ == "__main__":
    logger.info("Starting Gradio UI on port 7860")
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False)