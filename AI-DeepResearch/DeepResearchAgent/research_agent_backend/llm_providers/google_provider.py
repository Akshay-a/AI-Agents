import os
import logging
from typing import AsyncIterator, Optional, Dict, Any, List

import google.generativeai as genai
# Import specific exceptions if needed for finer-grained handling later
# from google.api_core import exceptions as google_exceptions
from google.generativeai.types import GenerationConfig, ContentDict, PartDict, HarmCategory, HarmBlockThreshold, RequestOptions

from .base_provider import BaseLLMProvider

logger = logging.getLogger(__name__)

# Default safety settings - potentially make these configurable
DEFAULT_SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
}


DEFAULT_REQUEST_OPTIONS = RequestOptions(timeout=120) # 120 seconds timeout

class GeminiProvider(BaseLLMProvider):
    """
    LLM Provider implementation for Google Gemini models using google-generativeai.
    """
    DEFAULT_MODEL = "gemini-2.0-flash-lite" # A generally available and capable model

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        """Initializes the Gemini provider."""
        resolved_model_name = model_name or self.DEFAULT_MODEL
        # Store model name before calling super().__init__ which calls _initialize_client
        self.model_name = resolved_model_name
        self.api_key = api_key # Store key temporarily
        self.model: Optional[genai.GenerativeModel] = None
        # Call super() AFTER setting attributes needed by _initialize_client
        super().__init__(api_key=api_key, model_name=resolved_model_name)


    def _initialize_client(self):
        """Initializes the Google Gemini client and model object."""
        loaded_api_key = self.api_key # Use provided key first
        if loaded_api_key is None:
            loaded_api_key = os.getenv("GOOGLE_API_KEY")
            if loaded_api_key is None:
                logger.error("GOOGLE_API_KEY environment variable not set and no api_key provided during initialization.")
                raise ValueError("GOOGLE_API_KEY must be set or api_key provided.")
            logger.info("Loaded Google API Key from GOOGLE_API_KEY environment variable.")
        else:
             logger.info("Using Google API Key provided during initialization.")

        try:
            # Configure the API key globally for the library
            genai.configure(api_key=loaded_api_key)
            logger.info(f"Configured Google GenAI library. Attempting to initialize model: {self.model_name}")

            # Create the specific model instance
            self.model = genai.GenerativeModel(
                model_name=self.model_name
                # system_instruction can be added here if needed globally
            )
            # Quick check to see if model seems accessible (optional, might incur small cost/quota)
            # try:
            #     self.count_tokens("test") # Simple check
            # except Exception as test_e:
            #      logger.warning(f"Initial test call (count_tokens) to model {self.model_name} failed: {test_e}. Check API key permissions and model name.")
                 # Don't raise here, let actual generate calls fail later

            logger.info(f"Successfully created GenerativeModel instance for '{self.model_name}'.")

        except Exception as e:
            logger.exception(f"Failed to initialize Google Gemini client/model for {self.model_name}: {e}")
            # Ensure self.model is None if init fails
            self.model = None
            raise RuntimeError(f"Gemini client/model initialization failed: {e}") from e

    def _prepare_generation_config(
        self,
        temperature: float,
        max_output_tokens: Optional[int],
        top_p: Optional[float],
        top_k: Optional[int]
    ) -> GenerationConfig:
        """Helper to create Gemini GenerationConfig dictionary."""
        config_dict = {}
        # Ensure values are not None before adding
        if temperature is not None:
            config_dict["temperature"] = temperature
        if max_output_tokens is not None:
            config_dict["max_output_tokens"] = max_output_tokens
        if top_p is not None:
            config_dict["top_p"] = top_p
        if top_k is not None:
            config_dict["top_k"] = top_k
        # Only create GenerationConfig if dict is not empty
        return GenerationConfig(**config_dict) if config_dict else None


    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_output_tokens: Optional[int] = 4096, # Increased default
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        safety_settings: Optional[Dict[HarmCategory, HarmBlockThreshold]] = DEFAULT_SAFETY_SETTINGS,
        request_options: Optional[RequestOptions] = DEFAULT_REQUEST_OPTIONS,
        **kwargs: Any
    ) -> str:
        """Generates text using the configured Gemini model."""
        if not self.model:
            raise RuntimeError("Gemini model is not initialized. Initialization might have failed.")
        if kwargs:
            logger.warning(f"Unused keyword arguments provided to Gemini generate: {kwargs}")

        generation_config = self._prepare_generation_config(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            top_p=top_p,
            top_k=top_k
        )

        # Ensure contents is a list
        contents_payload: List[ContentDict | str] = [prompt]

        try:
            logger.info(f"Sending request to Gemini model {self.model_name}. Prompt length: {len(prompt)} chars.")
            response = await self.model.generate_content_async(
                contents=contents_payload,
                generation_config=generation_config,
                safety_settings=safety_settings,
                request_options=request_options
            )

            # --- Robust Response Handling ---
            try:
                # Check for blocking first via prompt_feedback
                if response.prompt_feedback.block_reason != 0: # 0 means BLOCK_REASON_UNSPECIFIED (no block)
                     block_reason_str = response.prompt_feedback.block_reason.name
                     logger.error(f"Gemini generation blocked for prompt. Reason: {block_reason_str}. Safety Ratings: {response.prompt_feedback.safety_ratings}")
                     raise RuntimeError(f"Gemini generation blocked due to prompt safety. Reason: {block_reason_str}")

                # Check candidates and their finish reason
                if not response.candidates:
                    logger.error(f"Gemini generation failed. No candidates returned. Prompt Feedback: {response.prompt_feedback}")
                    raise RuntimeError("Gemini generation failed: No candidates in response.")

                candidate = response.candidates[0]
                finish_reason = candidate.finish_reason
                if finish_reason not in [1, 0]: # 1=STOP, 0=UNSPECIFIED (often ok)
                    finish_reason_str = finish_reason.name
                    logger.warning(f"Gemini generation finished with reason: {finish_reason_str}. Output might be incomplete or compromised. Safety Ratings: {candidate.safety_ratings}")
                    # Decide if this should be an error or just a warning
                    # raise RuntimeError(f"Gemini generation finished abnormally: {finish_reason_str}")

                # Extract text safely
                generated_text = "".join(part.text for part in candidate.content.parts if hasattr(part, 'text'))

                if not generated_text and finish_reason in [1, 0]:
                     logger.warning(f"Gemini generation successful (finish reason {finish_reason.name}), but produced empty text output.")
                     # Return empty string, but log it

                logger.info(f"Gemini generation successful. Finish Reason: {finish_reason.name}. Output length: {len(generated_text)} chars.")
                return generated_text

            except AttributeError as e:
                 logger.error(f"Error accessing attributes in Gemini response object: {e}. Response: {response}", exc_info=True)
                 raise RuntimeError(f"Failed to parse Gemini response structure: {e}") from e
            except IndexError as e:
                 logger.error(f"Error accessing candidates in Gemini response (likely empty): {e}. Response: {response}", exc_info=True)
                 raise RuntimeError("Failed to access response candidate (response might be empty or blocked).") from e

        except Exception as e:
            # Catch-all for API call errors, network issues, etc.
            logger.exception(f"Error during Gemini API call for generate: {e}")
            # You might want to check for specific google_exceptions here
            # if isinstance(e, google_exceptions.PermissionDenied): ...
            raise RuntimeError(f"Gemini API call failed: {e}") from e


    async def generate_stream(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_output_tokens: Optional[int] = 4096,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        safety_settings: Optional[Dict[HarmCategory, HarmBlockThreshold]] = DEFAULT_SAFETY_SETTINGS,
        request_options: Optional[RequestOptions] = DEFAULT_REQUEST_OPTIONS,
        **kwargs: Any
    ) -> AsyncIterator[str]:
        """Generates text stream using the configured Gemini model."""
        if not self.model:
            raise RuntimeError("Gemini model is not initialized.")
        if kwargs:
            logger.warning(f"Unused keyword arguments provided to Gemini generate_stream: {kwargs}")

        generation_config = self._prepare_generation_config(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            top_p=top_p,
            top_k=top_k
        )
        contents_payload: List[ContentDict | str] = [prompt]

        try:
            logger.info(f"Starting stream request to Gemini model {self.model_name}.")
            response_stream = await self.model.generate_content_async(
                contents=contents_payload,
                generation_config=generation_config,
                safety_settings=safety_settings,
                request_options=request_options,
                stream=True
            )

            async for chunk in response_stream:
                try:
                    # Check for blocking via prompt_feedback (might appear early or late)
                    if chunk.prompt_feedback.block_reason != 0:
                         block_reason_str = chunk.prompt_feedback.block_reason.name
                         logger.error(f"Gemini stream blocked. Reason: {block_reason_str}. Safety Ratings: {chunk.prompt_feedback.safety_ratings}")
                         raise RuntimeError(f"Gemini stream blocked due to prompt safety. Reason: {block_reason_str}")

                    if not chunk.candidates:
                         # This might happen if the stream ends due to error/blocking
                         logger.warning("Gemini stream chunk received with no candidates. Stream may have terminated early.")
                         continue # Skip empty candidate chunks

                    candidate = chunk.candidates[0]
                    finish_reason = candidate.finish_reason
                    if finish_reason not in [1, 0]: # 1=STOP, 0=UNSPECIFIED
                        finish_reason_str = finish_reason.name
                        logger.warning(f"Gemini stream chunk finished with reason: {finish_reason_str}.")

                    # Extract text safely from parts
                    text_chunk = "".join(part.text for part in candidate.content.parts if hasattr(part, 'text'))
                    if text_chunk: # Only yield if there's text
                        yield text_chunk

                except AttributeError as e:
                     logger.error(f"Error accessing attributes in Gemini stream chunk: {e}. Chunk: {chunk}", exc_info=True)
                     # Decide whether to continue or raise
                     continue # Try to continue with next chunk
                except IndexError as e:
                     logger.error(f"Error accessing candidates in Gemini stream chunk: {e}. Chunk: {chunk}", exc_info=True)
                     continue # Try to continue

            logger.info(f"Gemini streaming finished for prompt.")

        except Exception as e:
            logger.exception(f"Error during Gemini API stream call: {e}")
            raise RuntimeError(f"Gemini API stream call failed: {e}") from e

    def count_tokens(self, text: str) -> int:
        """Counts tokens using the Gemini model's tokenizer."""
        if not self.model:
            # Check if model failed initialization
            logger.error("Cannot count tokens: Gemini model is not initialized.")
            raise RuntimeError("Gemini model is not initialized.")
        try:
            # Ensure contents is a list for count_tokens as well
            contents_payload: List[ContentDict | str] = [text]
            response = self.model.count_tokens(contents=contents_payload)
            token_count = response.total_tokens
            logger.debug(f"Counted {token_count} tokens for text length {len(text)}.")
            return token_count
        except Exception as e:
            # Log specific errors if possible (e.g., invalid input)
            logger.exception(f"Error during Gemini token counting for model {self.model_name}: {e}")
            raise RuntimeError(f"Gemini token counting failed: {e}") from e