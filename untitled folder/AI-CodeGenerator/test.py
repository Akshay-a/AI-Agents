from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
import logging

# Initialize the logger
logging.basicConfig(level=logging.INFO)

class AIClient:
    """Managed AI API client with error handling"""

    def __init__(self, model_name="deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B"):
        self.model_name = model_name
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(model_name,trust_remote_code=True)
        self.history = []  # Maintain conversation history

    def get_completion(self, messages: list) -> str:
        """Safe API request handler with retries"""
        try:
            inputs = self.tokenizer("\n".join(messages), return_tensors="pt")
            outputs = self.model.generate(**inputs, max_length=1024)
            response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            # Append the current messages and response to history
            self.history.extend(messages + [response])
            return response
        except Exception as e:
            logging.error(f"API request failed: {str(e)}")
            return "An error occurred. Please try again later."
n    
# Example usage
ai_client = AIClient(model_name="deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B")

context = ["Hello, how can I assist you today?"]
response = ai_client.get_completion(context)
print(response)

# Add more context to the session
additional_context = ["I need help with setting up a local AI model."]
updated_response = ai_client.get_completion(additional_context)
print(updated_response)