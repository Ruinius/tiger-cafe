"""
Gemini API client with rate limiting, retry logic, throttling, and processing queue
"""

import random
import threading
import time
from functools import wraps

from google import genai

from config.config import DEFAULT_MODEL, EMBEDDING_MODEL, GEMINI_API_KEY, TEMPERATURE

# Initialize Gemini client
_client = genai.Client(api_key=GEMINI_API_KEY)

# Rate limiting configuration
MIN_DELAY_BETWEEN_CALLS = 0.5  # Minimum 500ms between API calls (increased from 100ms)
MAX_DELAY_BETWEEN_CALLS = 2.0  # Maximum 2 seconds between API calls (increased from 500ms)
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 2.0  # Start with 2 seconds delay (increased from 1s)
MAX_RETRY_DELAY = 30.0  # Max 30 seconds delay (increased from 10s)

# Processing queue configuration - limit concurrent API calls
MAX_CONCURRENT_LLM_CALLS = 1  # Maximum concurrent LLM (generate_content) calls
MAX_CONCURRENT_EMBEDDING_CALLS = 3  # Maximum concurrent embedding calls

# Semaphores to limit concurrent API calls
_llm_semaphore = threading.Semaphore(MAX_CONCURRENT_LLM_CALLS)
_embedding_semaphore = threading.Semaphore(MAX_CONCURRENT_EMBEDDING_CALLS)

# Track last API call time for throttling (thread-safe)
_last_call_time = 0
_throttle_lock = threading.Lock()


def _throttle():
    """Add delay between API calls to prevent overwhelming the API"""
    global _last_call_time
    with _throttle_lock:
        current_time = time.time()
        time_since_last_call = current_time - _last_call_time

        # Calculate delay with jitter to avoid thundering herd
        delay = MIN_DELAY_BETWEEN_CALLS + random.uniform(
            0, MAX_DELAY_BETWEEN_CALLS - MIN_DELAY_BETWEEN_CALLS
        )

        if time_since_last_call < delay:
            sleep_time = delay - time_since_last_call
            time.sleep(sleep_time)

        _last_call_time = time.time()


def _retry_with_backoff(func):
    """Decorator to retry API calls with exponential backoff"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        last_exception = None
        delay = INITIAL_RETRY_DELAY

        for attempt in range(MAX_RETRIES):
            try:
                _throttle()  # Throttle before each attempt
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                error_str = str(e).lower()

                # Check if it's a rate limit or quota error
                is_rate_limit = any(
                    keyword in error_str
                    for keyword in [
                        "rate limit",
                        "quota",
                        "429",
                        "too many requests",
                        "resource exhausted",
                        "service unavailable",
                        "503",
                    ]
                )

                # If it's not a rate limit error and not the last attempt, raise immediately
                if not is_rate_limit and attempt < MAX_RETRIES - 1:
                    raise

                # If it's the last attempt, raise the exception
                if attempt == MAX_RETRIES - 1:
                    raise

                # Exponential backoff with jitter
                # For rate limit errors, use longer backoff
                if is_rate_limit:
                    # More aggressive backoff for rate limits
                    jitter = random.uniform(0, delay * 0.2)  # 20% jitter for rate limits
                    sleep_time = min(delay + jitter, MAX_RETRY_DELAY)
                    print(
                        f"Rate limit error (attempt {attempt + 1}/{MAX_RETRIES}): {str(e)}. Retrying in {sleep_time:.2f}s..."
                    )
                else:
                    jitter = random.uniform(0, delay * 0.1)  # 10% jitter for other errors
                    sleep_time = min(delay + jitter, MAX_RETRY_DELAY)
                    print(
                        f"API call failed (attempt {attempt + 1}/{MAX_RETRIES}): {str(e)}. Retrying in {sleep_time:.2f}s..."
                    )
                time.sleep(sleep_time)
                delay *= 2  # Exponential backoff

        # Should never reach here, but just in case
        raise last_exception

    return wrapper


@_retry_with_backoff
def generate_embedding_safe(
    text: str, max_chars: int = 20000, task_type: str = "retrieval_document"
) -> list[float]:
    """
    Generate embedding with rate limiting, retry logic, and processing queue.
    Uses a semaphore to limit concurrent embedding API calls.

    Args:
        text: Text to generate embedding for
        max_chars: Maximum characters to use for embedding
        task_type: Task type for embedding ("retrieval_document" or "retrieval_query")

    Returns:
        List of floats representing the embedding vector
    """
    # Acquire semaphore to limit concurrent calls
    _embedding_semaphore.acquire()
    try:
        # Truncate text if it's too long
        if len(text) > max_chars:
            text = text[:max_chars]
            print(f"Warning: Text truncated to {max_chars} characters for embedding generation")

        # The new google.genai API uses 'contents' (plural) parameter
        result = _client.models.embed_content(model=EMBEDDING_MODEL, contents=text)
        # The result has 'embeddings' (plural) attribute which is a list of ContentEmbedding objects
        if isinstance(result, dict):
            # Handle dict response format
            embeddings = result.get("embeddings", result.get("embedding"))
            if isinstance(embeddings, list) and len(embeddings) > 0:
                embedding_obj = embeddings[0]
                # Extract values from ContentEmbedding object
                if hasattr(embedding_obj, "values"):
                    return embedding_obj.values
                elif isinstance(embedding_obj, dict):
                    return embedding_obj.get("values", embedding_obj)
                return embedding_obj
            return embeddings
        else:
            # Handle object response format - result.embeddings is a list of ContentEmbedding objects
            embeddings = result.embeddings
            if isinstance(embeddings, list) and len(embeddings) > 0:
                embedding_obj = embeddings[0]
                # Extract values from ContentEmbedding object
                if hasattr(embedding_obj, "values"):
                    return embedding_obj.values
                elif isinstance(embedding_obj, dict):
                    return embedding_obj.get("values", embedding_obj)
                return embedding_obj
            return embeddings
    finally:
        # Always release semaphore, even if an error occurs
        _embedding_semaphore.release()


@_retry_with_backoff
def generate_content_safe(
    prompt: str, model_name: str | None = None, temperature: float | None = None
) -> str:
    """
    Generate content with rate limiting, retry logic, and processing queue.
    Uses a semaphore to limit concurrent LLM API calls.

    Args:
        prompt: Prompt text
        model_name: Model name (defaults to DEFAULT_MODEL)
        temperature: Temperature setting (defaults to TEMPERATURE)

    Returns:
        Generated text response
    """
    # Acquire semaphore to limit concurrent calls
    _llm_semaphore.acquire()
    try:
        response = _client.models.generate_content(
            model=model_name or DEFAULT_MODEL,
            contents=prompt,
            config={
                "temperature": temperature if temperature is not None else TEMPERATURE,
            },
        )
        # Handle both dict and object response formats
        if isinstance(response, dict):
            return response.get("text", str(response)).strip()
        else:
            # Try common attribute names for text response
            text = (
                getattr(response, "text", None)
                or getattr(response, "content", None)
                or str(response)
            )
            return text.strip() if text else str(response).strip()
    finally:
        # Always release semaphore, even if an error occurs
        _llm_semaphore.release()


def get_model_safe(model_name: str | None = None, temperature: float | None = None):
    """
    Get a model reference (for cases where you need the model object).
    Note: This doesn't make API calls, so no throttling needed.

    Args:
        model_name: Model name (defaults to DEFAULT_MODEL)
        temperature: Temperature setting (defaults to TEMPERATURE)

    Returns:
        Model reference (returns the client for compatibility)
    """
    # In the new API, we return the client itself since models are accessed via client.models
    return _client
