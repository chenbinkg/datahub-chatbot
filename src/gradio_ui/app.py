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
        verbose_mode = gr.Checkbox(label="Show Reasoning", value=False)
        clear = gr.Button("Clear")
        
        def respond(message, chat_history, token, mcp_type, verbose):
            if not token:
                return chat_history + [{"role": "assistant", "content": "Please login first"}], ""
            
            # Add user message to history
            chat_history.append({"role": "user", "content": message})
            
            # Get response from MCP server via Bedrock agent
            try:
                print(f"Invoking Bedrock Agent - ID: {BEDROCK_AGENT_ID}, Alias: {BEDROCK_AGENT_ALIAS_ID}")
                print(f"Message: {message}, MCP Type: {mcp_type}, Show Reasoning: {verbose}")
                
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
                reasoning_steps = []
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
                                trace_outer = event.get('trace', {})
                                trace_inner = trace_outer.get('trace', {})
                                orchestration_trace = trace_inner.get('orchestrationTrace', {})
                                
                                # Capture reasoning steps for verbose mode
                                if verbose and 'modelInvocationOutput' in orchestration_trace:
                                    model_output = orchestration_trace['modelInvocationOutput']
                                    if 'rawResponse' in model_output and 'content' in model_output['rawResponse']:
                                        content_json = json.loads(model_output['rawResponse']['content'])
                                        content_array = content_json.get("content", [])
                                        # Extract thinking content from the content array
                                        import re
                                        # print("content array length: ", len(content_array))
                                        if content_array:
                                            for content_item in content_array:
                                                if 'text' in content_item:
                                                    text_content = content_item.get("text", "")
                                                    # print(f"Text content: {text_content}")
                                                    if text_content:
                                                        if '</thinking>' in text_content:
                                                            thinking_match = re.search(r'<thinking>(.*?)</thinking>', text_content, re.DOTALL)
                                                            if thinking_match:
                                                                thinking_text = thinking_match.group(1).strip()
                                                                reasoning_steps.append(f"🤔 **Agent Thinking**: {thinking_text}")
                                                                # print(f"Thinking text: {thinking_text}")
                                                        if '</answer>' in text_content:
                                                            answer_match = re.search(r'<answer>(.*?)</answer>', text_content, re.DOTALL)
                                                            if answer_match:
                                                                answer_text = answer_match.group(1).strip()
                                                                reasoning_steps.append(f"💡 **Agent Answer**: {answer_text[:100]}...")
                                                                # print(f"Answer text: {answer_text}")

                                
                                # Capture tool results for verbose mode
                                if verbose and 'observation' in orchestration_trace:
                                    observation = orchestration_trace['observation']
                                    if 'actionGroupInvocationOutput' in observation:
                                        action_output = observation['actionGroupInvocationOutput']
                                        if 'text' in action_output:
                                            try:
                                                tool_result = json.loads(action_output['text'])
                                                print("Tool result:", tool_result)
                                                if tool_result.get('status') == 'success':
                                                    result_data = tool_result.get('result', {})
                                                    reasoning_steps.append(f"✅ **Tool Result**: {str(result_data)[:100]}...")
                                                else:
                                                    reasoning_steps.append(f"❌ **Tool Error**: {tool_result.get('message', 'Unknown error')}")
                                            except:
                                                reasoning_steps.append(f"📄 **Tool Output**: {action_output['text'][:100]}...")
                                
                                # print(f"Trace event: {trace}")  # Comment out to reduce log noise
                    except Exception as stream_error:
                        print(f"Error processing stream: {stream_error}")
                        result_text = f"Stream processing error: {str(stream_error)}"
                    
                    # Add reasoning steps if verbose mode is enabled
                    if verbose and reasoning_steps:
                        reasoning_text = "\n\n**🔍 Reasoning Process:**\n" + "\n".join(reasoning_steps) + "\n\n---\n\n"
                        result_text = reasoning_text + result_text
                    
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
        
        msg.submit(respond, [msg, chatbot, token_state, mcp_type, verbose_mode], [chatbot, msg])
        clear.click(lambda: None, None, chatbot, queue=False)
        
    login_button.click(
        authenticate,
        [username_input, password_input],
        [login_output, token_state]
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)