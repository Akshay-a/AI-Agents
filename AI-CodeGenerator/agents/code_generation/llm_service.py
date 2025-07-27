"""
Unified LLM Service for Code Generation Agent

This service provides a unified interface for LLM calls across the code generation system.
It extends the existing llm_handler functionality with additional methods for migration,
enhancement, and other code generation tasks.
"""

import os
import sys
import logging
from typing import Optional, Dict, Any

# Add root directory to path to import llm_handler
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if root_dir not in sys.path:
    sys.path.append(root_dir)

try:
    import llm_handler
    import config
    LLM_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Failed to import llm_handler: {e}")
    LLM_AVAILABLE = False

logger = logging.getLogger(__name__)


class UnifiedLLMService:
    """
    Unified LLM service that provides consistent interface for all code generation tasks.
    Extends the existing llm_handler with additional methods for migration, enhancement, etc.
    """
    
    def __init__(self):
        self.llm_available = LLM_AVAILABLE
        if not self.llm_available:
            logger.warning("LLM handler not available, using mock responses")
    
    def generate_initial_code(self, prompt: str) -> str:
        """
        Generate initial code using the existing llm_handler.
        This maintains compatibility with the existing system.
        """
        if not self.llm_available:
            return self._mock_response(prompt)
        
        try:
            result = llm_handler.generate_initial_code(prompt)
            return result if result else self._mock_response(prompt)
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return self._mock_response(prompt)
    
    def migrate_code(self, source_code: str, source_language: str, target_language: str, requirements: str) -> str:
        """
        Migrate code from one language/technology to another.
        """
        if not self.llm_available:
            return self._mock_migration_response(source_language, target_language)
        
        prompt = self._build_migration_prompt(source_code, source_language, target_language, requirements)
        
        try:
            result = llm_handler.generate_initial_code(prompt)
            return result if result else self._mock_migration_response(source_language, target_language)
        except Exception as e:
            logger.error(f"Migration LLM call failed: {e}")
            return self._mock_migration_response(source_language, target_language)
    
    def enhance_code(self, existing_code: str, enhancement_requirements: str, language: str = "python") -> str:
        """
        Enhance existing code with new features or improvements.
        """
        if not self.llm_available:
            return self._mock_enhancement_response(existing_code)
        
        prompt = self._build_enhancement_prompt(existing_code, enhancement_requirements, language)
        
        try:
            result = llm_handler.generate_initial_code(prompt)
            return result if result else self._mock_enhancement_response(existing_code)
        except Exception as e:
            logger.error(f"Enhancement LLM call failed: {e}")
            return self._mock_enhancement_response(existing_code)
    
    def fix_bugs(self, faulty_code: str, error_message: str, requirements: str) -> str:
        """
        Fix bugs in code using the existing debug_code functionality.
        """
        if not self.llm_available:
            return self._mock_debug_response(faulty_code)
        
        try:
            result = llm_handler.debug_code(requirements, faulty_code, error_message)
            return result if result else self._mock_debug_response(faulty_code)
        except Exception as e:
            logger.error(f"Debug LLM call failed: {e}")
            return self._mock_debug_response(faulty_code)
    
    def _build_migration_prompt(self, source_code: str, source_language: str, target_language: str, requirements: str) -> str:
        """Build prompt for code migration."""
        return f"""
You are an expert software engineer specializing in code migration between different programming languages and technologies.

Your task is to migrate the following {source_language} code to {target_language} while preserving all functionality and following best practices.

Migration Requirements:
{requirements}

Migration Guidelines:
1. Preserve all business logic and functionality
2. Follow {target_language} best practices and idioms
3. Use appropriate {target_language} libraries and frameworks
4. Maintain proper error handling
5. Add comprehensive documentation
6. Ensure the migrated code is production-ready
7. If migrating from LabVIEW, focus on:
   - Converting VI logic to appropriate functions/classes
   - Mapping LabVIEW data types to {target_language} equivalents
   - Converting LabVIEW controls/indicators to appropriate UI or data structures
   - Preserving mathematical and signal processing operations

Source {source_language} Code:
```{source_language.lower()}
{source_code}
```

Please provide the complete migrated {target_language} code enclosed in markdown code blocks:
"""
    
    def _build_enhancement_prompt(self, existing_code: str, requirements: str, language: str) -> str:
        """Build prompt for code enhancement."""
        return f"""
You are an expert {language} developer. Your task is to enhance the existing code according to the provided requirements.

Enhancement Requirements:
{requirements}

Enhancement Guidelines:
1. Preserve existing functionality
2. Follow {language} best practices
3. Add proper error handling
4. Include comprehensive documentation
5. Optimize performance where possible
6. Maintain code readability and maintainability
7. Add appropriate tests if requested

Existing {language} Code:
```{language}
{existing_code}
```

Please provide the enhanced code enclosed in markdown code blocks:
"""
    
    def _mock_response(self, prompt: str) -> str:
        """Generate mock response when LLM is not available."""
        return f"""# Mock LLM Response - LLM Service Not Available
# This is a placeholder response generated when the real LLM service is unavailable
# Original prompt: {prompt[:100]}...

def mock_generated_function():
    \"\"\"
    This is a mock function generated because the LLM service is not properly configured.
    To fix this:
    1. Ensure GOOGLE_API_KEY is set in your environment
    2. Install required dependencies: pip install google-generativeai
    3. Check that config.py is properly configured
    \"\"\"
    print("Mock function - please configure LLM service")
    return "mock_result"

if __name__ == "__main__":
    mock_generated_function()
"""
    
    def _mock_migration_response(self, source_language: str, target_language: str) -> str:
        """Generate mock migration response."""
        return f"""# Mock Migration Response - LLM Service Not Available
# Migration: {source_language} -> {target_language}
# This is a placeholder response generated when the real LLM service is unavailable

def migrated_function():
    \"\"\"
    This is a mock migration result because the LLM service is not properly configured.
    
    For proper {source_language} to {target_language} migration:
    1. Configure the LLM service with valid API keys
    2. Ensure the source code is properly parsed
    3. Provide detailed migration requirements
    \"\"\"
    print(f"Mock migration from {source_language} to {target_language}")
    return "migration_result"

# Example usage
if __name__ == "__main__":
    result = migrated_function()
    print(f"Migration result: {result}")
"""
    
    def _mock_enhancement_response(self, existing_code: str) -> str:
        """Generate mock enhancement response."""
        return f"""# Mock Enhancement Response - LLM Service Not Available
# Original code length: {len(existing_code)} characters
# This is a placeholder response generated when the real LLM service is unavailable

{existing_code}

# Mock enhancement added below:
def enhanced_feature():
    \"\"\"
    This is a mock enhancement because the LLM service is not properly configured.
    Configure the LLM service to get real code enhancements.
    \"\"\"
    print("Mock enhancement - please configure LLM service")
    return "enhanced_result"
"""
    
    def _mock_debug_response(self, faulty_code: str) -> str:
        """Generate mock debug response."""
        return f"""# Mock Debug Response - LLM Service Not Available
# This is a placeholder response generated when the real LLM service is unavailable

{faulty_code}

# Mock debug fix added:
print("Mock debug fix - please configure LLM service")
# The above code has been 'fixed' with this mock response
"""


# Create singleton instance
_llm_service_instance = None

def get_llm_service() -> UnifiedLLMService:
    """Get singleton instance of the LLM service."""
    global _llm_service_instance
    if _llm_service_instance is None:
        _llm_service_instance = UnifiedLLMService()
    return _llm_service_instance


# Legacy compatibility - expose the same interface as the original llm_handler
def generate_initial_code(prompt: str) -> str:
    """Legacy compatibility function."""
    service = get_llm_service()
    return service.generate_initial_code(prompt)


def debug_code(requirements: str, faulty_code: str, error_message: str) -> str:
    """Legacy compatibility function."""
    service = get_llm_service()
    return service.fix_bugs(faulty_code, error_message, requirements) 