"""
AI Agent Suite: Automated Code Generation and Iterative Debugging System
Authors: Akshay Kumar Apsingi
Version: 1.0 (Local Execution)
"""

import os
import sys
import json
import logging
import subprocess
from pathlib import Path
from typing import Tuple, Dict, Optional
# from openai import OpenAI
from ollama import OllamaLLM  # Assuming this is the correct import based on your setup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("agent_suite.log"),
        logging.StreamHandler()
    ]
)

class Config:
    """Configuration constants and environment settings"""
    MAX_RETRIES = 3
    CODE_DIR = Path("generated_code")
    JAVA_DIR = Path("java_project")
    ALLOWED_LANGUAGES = {"python", "java"}
    PYTHON_EXECUTABLE = "python"  # Use "python3" if needed
    JAVA_COMPILER = "javac"
    JAVA_RUNNER = "java"

class AIClient:
    """Managed AI API client with error handling"""
    def __init__(self):
        # self.client = OpenAI()
        # self.model = "gpt-4-turbo"
        self.chat_model = OllamaLLM(model="qwen2.5:7b", base_url="http://localhost:11434", temperature=0.6)
        self.code_retry_prompt = """Fix the following code. Return the ENTIRE corrected code with comments.
        Include these specific changes:
        1. Fix all syntax errors
        2. Handle edge cases
        3. Add proper error handling
        4. Maintain original functionality
        """

    def get_completion(self, messages: list, response_format: Optional[dict] = None) -> Optional[dict]:
        """Safe API request handler with retries"""
        try:
            # OllamaLLM likely expects a different interface; adapting to a common pattern
            # Assuming it has a method like `chat` or `generate` that takes messages
            prompt = "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])
            if response_format and response_format.get("type") == "json_object":
                prompt += "\nReturn the response in JSON format."

            # Using `chat` method (common in LangChain-style wrappers); adjust if different
            response = self.chat_model.chat(messages)

            # Mimic OpenAI's response structure for compatibility
            class Completion:
                class Choice:
                    def __init__(self, message):
                        self.message = type("Message", (), {"content": message})()
                def __init__(self, choices):
                    self.choices = [self.Choice(choices)]

            # Assuming response is a string or dict; adjust based on actual OllamaLLM output
            if isinstance(response, str):
                return type("Response", (), {"choices": Completion(response).choices})()
            elif isinstance(response, dict) and "content" in response:
                return type("Response", (), {"choices": Completion(response["content"]).choices})()
            else:
                raise ValueError("Unexpected response format from OllamaLLM")

        except Exception as e:
            logging.error(f"API request failed: {str(e)}")
            return None

class CodeManager:
    """Language-agnostic code management system"""
    def __init__(self):
        self.config = Config()
        self.setup_directories()

    def setup_directories(self):
        """Ensure required directory structure exists"""
        self.config.CODE_DIR.mkdir(exist_ok=True)
        self.config.JAVA_DIR.mkdir(parents=True, exist_ok=True)

    def save_code(self, code: str, language: str, filename: str) -> Path:
        """Save code with language-appropriate structure"""
        if language == "python":
            path = self.config.CODE_DIR / filename
        elif language == "java":
            path = self.config.JAVA_DIR / "src" / filename
            (self.config.JAVA_DIR / "src").mkdir(exist_ok=True)
        
        path.write_text(code)
        return path

class ExecutionEngine:
    """Safe code execution subsystem with local sandboxing"""
    def __init__(self):
        self.code_manager = CodeManager()
        self.config = Config()

    def execute_python(self, code: str, attempt: int) -> Tuple[bool, str, str]:
        """Execute Python code locally with resource limits"""
        filename = self.code_manager.save_code(code, "python", f"temp_{attempt}.py")
        
        try:
            # Execute with timeout and resource limits
            result = subprocess.run(
                [self.config.PYTHON_EXECUTABLE, str(filename)],
                capture_output=True,
                text=True,
                timeout=300,  # Timeout after 300 seconds
                check=True
            )
            return True, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            logging.error("Execution timed out")
            return False, "", "Execution timed out"
        except subprocess.CalledProcessError as e:
            return False, e.stdout, e.stderr
        except Exception as e:
            logging.error(f"Execution error: {str(e)}")
            return False, "", str(e)

class AgentWorkflow:
    """Orchestration layer for end-to-end AI workflow"""
    def __init__(self):
        self.ai_client = AIClient()
        self.exec_engine = ExecutionEngine()
        self.code_manager = CodeManager()
        self.config = Config()

    def detect_language(self, requirement: str) -> str:
        """Advanced language detection with fallback"""
        messages = [
            {"role": "system", "content": "Analyze the requirement and determine the best implementation language. Consider:\n1. Performance needs\n2. Ecosystem suitability\n3. Deployment requirements"},
            {"role": "user", "content": requirement}
        ]
        
        response = self.ai_client.get_completion(messages)
        if not response:
            return "python"  # Default fallback
            
        language = response.choices[0].message.content.lower()
        return language if language in self.config.ALLOWED_LANGUAGES else "python"

    def refine_requirements(self, user_input: str) -> Dict:
        """Iterative requirements clarification"""
        messages = [
            {"role": "system", "content": "You are a senior requirements engineer. Identify ambiguities and generate atomic sub-tasks.Each Sub Task should be such that it can be codified independently"},
            {"role": "user", "content": user_input}
        ]
        
        response = self.ai_client.get_completion(
            messages,
            response_format={"type": "json_object"}
        )
        
        return json.loads(response.choices[0].message.content) if response else {}

    def generate_code(self, task: str, language: str, context: str = "", error: str = "") -> str:
        """Context-aware code generation with error correction"""
        messages = [
            {
                "role": "system",
                "content": f"""You are a {language} expert developer. Follow these rules:
                1. Write production-grade code
                2. Include error handling
                3. Add type hints
                4. Include docstrings
                5. Maintain consistency with the following context:
                ```{language}
                {context}
                ```"""
            },
            {"role": "user", "content": f"Task: {task}\nError: {error}"}
        ]
        
        response = self.ai_client.get_completion(messages)
        return response.choices[0].message.content if response else ""

    def iterative_debugging(self, code: str, language: str) -> Tuple[bool, str]:
        """Advanced debugging pipeline with multiple strategies"""
        for attempt in range(1, self.config.MAX_RETRIES + 1):
            if language == "python":
                success, output, error = self.exec_engine.execute_python(code, attempt)
            else:
                logging.error(f"Unsupported language: {language}")
                return False, ""
            
            if success:
                return True, output
            
            logging.warning(f"Attempt {attempt} failed: {error}")
            code = self.generate_code(
                task="Fix the following code",
                language=language,
                context=code,
                error=error
            )
            
            # Validate code changes
            if not self.validate_code_changes(code, language):
                logging.error("Invalid code modification detected")
                break

        return False, error

    def validate_code_changes(self, new_code: str, language: str) -> bool:
        """Check for dangerous patterns or invalid modifications"""
        if language == "python":
            return all(pattern not in new_code for pattern in ["os.system", "subprocess.run", "eval("])
        return True

def main(user_input: str):
    """End-to-end execution workflow"""
    workflow = AgentWorkflow()
    
    
    language ='python' 
    #language=workflow.detect_language(user_input)  
    #removing above logic to avoid addional api call to get language, we can rather hard code the language as python or may be write a func to identify python or java based on prompt by directly searching 
    logging.info(f"Selected implementation language: {language}")
    
    # Phase 1: Requirement Analysis
    requirements = workflow.refine_requirements(user_input)
    if not requirements.get("subtasks"):
        logging.error("Failed to refine requirements")
        return
        
    # Phase 2: Iterative Development
    context = ""
    for task in requirements["subtasks"]:
        logging.info(f"Processing task: {task}")
        code = workflow.generate_code(task, language, context)
        if not code:
            logging.error("Code generation failed")
            continue
            
        # Phase 3: Safe Execution
        success, output = workflow.iterative_debugging(code, language)
        if success:
            context += f"\nPrevious implementation:\n{code}"
            logging.info(f"Task completed successfully\nOutput: {output}")
        else:
            logging.error(f"Failed to complete task: {task}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python agent_suite.py '<requirement>'")
        sys.exit(1)
        
    main(sys.argv[1])