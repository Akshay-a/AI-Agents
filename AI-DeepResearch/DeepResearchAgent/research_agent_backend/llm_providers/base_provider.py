import os
import logging
from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional, Dict, Any

logger = logging.getLogger(__name__)

class BaseLLMProvider(ABC):
    """
    Abstract base class for Large Language Model providers.
    Defines a common interface for interacting with different LLMs.
    """
    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        """
        Initializes the provider.

        Args:
            api_key (Optional[str]): The API key for the provider. If None,
                                     the implementation should attempt to load it
                                     from environment variables.
            model_name (Optional[str]): The specific model name to use.
                                        If None, a default should be used by the
                                        implementation or an error raised.
        """
        if not model_name:
            # Concrete implementations should define their default or raise error
            logger.warning(f"{self.__class__.__name__}: model_name not provided. Implementation must handle default or raise error.")
        self.api_key = api_key
        self.model_name = model_name
        self._initialize_client() # Call hook for concrete implementation

    @abstractmethod
    def _initialize_client(self):
        """
        Abstract method for concrete implementations to initialize their specific
        API client using the provided api_key and model_name.
        Should handle API key loading from environment if self.api_key is None.
        Should raise ValueError if API key is missing.
        Should set up the client object (e.g., self.client).
        """
        pass

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_output_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        **kwargs: Any # For additional provider-specific parameters
    ) -> str:
        """
        Generates text based on a given prompt.

        Args:
            prompt (str): The input prompt.
            temperature (float): Controls randomness (0.0=deterministic, 1.0=creative).
            max_output_tokens (Optional[int]): Maximum number of tokens to generate.
            top_p (Optional[float]): Nucleus sampling parameter.
            top_k (Optional[int]): Top-k sampling parameter.
            **kwargs: Additional provider-specific arguments.

        Returns:
            str: The generated text.

        Raises:
            Exception: If generation fails (specific exceptions depend on implementation).
        """
        pass

    @abstractmethod
    async def generate_stream(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_output_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        **kwargs: Any
    ) -> AsyncIterator[str]:
        """
        Generates text based on a given prompt, yielding chunks as they become available.

        Args:
            prompt (str): The input prompt.
            temperature (float): Controls randomness.
            max_output_tokens (Optional[int]): Maximum number of tokens to generate.
            top_p (Optional[float]): Nucleus sampling parameter.
            top_k (Optional[int]): Top-k sampling parameter.
            **kwargs: Additional provider-specific arguments.

        Yields:
            str: Chunks of the generated text.

        Raises:
            Exception: If generation fails.
        """
        # Ensure the method is recognized as an async generator even if not implemented
        # This line is not strictly necessary if the abstract method is implemented correctly,
        # but it makes the intent clear.
        if False: # pragma: no cover
            yield
        pass


    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """
        Counts the number of tokens in a given text according to the provider's
        tokenizer for the configured model.

        Args:
            text (str): The text to count tokens for.

        Returns:
            int: The number of tokens.

        Raises:
            Exception: If token counting fails.
        """
        pass

    def get_model_name(self) -> Optional[str]:
        """Returns the configured model name."""
        return self.model_name