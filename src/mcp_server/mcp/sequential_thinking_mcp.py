import boto3
import json
import os
from typing import Dict, Any, Optional, List
from .base_mcp import BaseMCP

class SequentialThinkingMCP(BaseMCP):
    """MCP implementation for sequential thinking and complex reasoning"""
    
    def __init__(self):
        """Initialize Sequential Thinking MCP"""
        self.default_region = os.environ.get("AWS_REGION", "ap-southeast-2")
        self.bedrock_clients = {}
        
    def _get_bedrock_client(self, region=None):
        """Get or create a Bedrock client for the specified region"""
        region = region or self.default_region
        if region not in self.bedrock_clients:
            self.bedrock_clients[region] = boto3.client(
                'bedrock-runtime',
                region_name=region
            )
        return self.bedrock_clients[region]
        
    def process(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> Any:
        """
        Process a query using sequential thinking approach
        
        Args:
            query: The query string to process
            parameters: Optional parameters including:
                - steps: Number of reasoning steps (default: 3)
                - model_id: Bedrock model ID (default: anthropic.claude-sonnet-4-20250514-v1:0)
                - max_tokens: Maximum tokens for response (default: 1000)
                - region: AWS region where the model is available (default: us-east-1)
                
        Returns:
            The result of sequential thinking process
        """
        if parameters is None:
            parameters = {}
            
        steps = parameters.get("steps", 3)
        model_id = parameters.get("model_id", "anthropic.claude-sonnet-4-20250514-v1:0")
        max_tokens = parameters.get("max_tokens", 1000)
        model_region = parameters.get("region", "us-east-1")  # Claude models are in us-east-1
        
        try:
            # Step 1: Break down the problem
            breakdown = self._invoke_model(
                f"Break down the following problem into {steps} logical steps:\n\n{query}",
                model_id,
                max_tokens,
                model_region
            )
            
            # Step 2: Execute each step
            intermediate_results = []
            steps_list = self._parse_steps(breakdown)
            
            for i, step in enumerate(steps_list):
                context = "\n".join([
                    f"Step {j+1} result: {result}" 
                    for j, result in enumerate(intermediate_results)
                ])
                
                prompt = f"""
                Original query: {query}
                
                Problem breakdown:
                {breakdown}
                
                Previous results:
                {context}
                
                Execute step {i+1}: {step}
                """
                
                result = self._invoke_model(prompt, model_id, max_tokens, model_region)
                intermediate_results.append(result)
            
            # Step 3: Synthesize final answer
            synthesis_prompt = f"""
            Original query: {query}
            
            Problem breakdown:
            {breakdown}
            
            Step-by-step results:
            {"\n".join([f"Step {i+1}: {result}" for i, result in enumerate(intermediate_results)])}
            
            Synthesize a final, comprehensive answer to the original query based on these steps.
            """
            
            final_answer = self._invoke_model(synthesis_prompt, model_id, max_tokens, model_region)
            
            return {
                "original_query": query,
                "problem_breakdown": breakdown,
                "intermediate_steps": [
                    {"step": step, "result": result}
                    for step, result in zip(steps_list, intermediate_results)
                ],
                "final_answer": final_answer
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def _invoke_model(self, prompt: str, model_id: str, max_tokens: int, region: str = None) -> str:
        """Invoke Bedrock model with prompt"""
        if model_id.startswith("anthropic.claude"):
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "temperature": 0.7,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }
        else:
            body = {
                "inputText": prompt,
                "textGenerationConfig": {
                    "maxTokenCount": max_tokens,
                    "temperature": 0.7
                }
            }
        
        # Get the appropriate client for the region
        client = self._get_bedrock_client(region)
        
        response = client.invoke_model(
            modelId=model_id,
            body=json.dumps(body)
        )
        
        response_body = json.loads(response.get("body").read())
        
        if model_id.startswith("anthropic.claude"):
            return response_body.get("content", [{}])[0].get("text", "")
        else:
            return response_body.get("results", [{}])[0].get("outputText", "")
    
    def _parse_steps(self, breakdown: str) -> List[str]:
        """Parse steps from the problem breakdown"""
        lines = breakdown.strip().split("\n")
        steps = []
        
        for line in lines:
            line = line.strip()
            if line and (line.startswith("Step") or line.startswith("1.") or line.startswith("1)")):
                # Remove step number prefix
                step_text = line.split(":", 1)[-1] if ":" in line else line
                step_text = step_text.strip()
                steps.append(step_text)
                
        # If no steps were found, treat the entire breakdown as one step
        if not steps:
            steps = [breakdown]
            
        return steps