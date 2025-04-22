from .base_provider import BaseLLMProvider
from .google_provider import GeminiProvider


# Optional: Factory function to get provider based on config
def get_provider(provider_name: str = "gemini", **kwargs) -> BaseLLMProvider:
    provider_name = provider_name.lower()
    if provider_name == "gemini":
        return GeminiProvider(**kwargs)
    # elif provider_name == "openai":
    #     return OpenAIProvider(**kwargs)
    else:
        raise ValueError(f"Unknown LLM provider: {provider_name}")