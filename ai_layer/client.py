"""
ai_layer/client.py

The AI "transport" layer: one interface (AIClient) and its concrete
implementations.

- AIClient     : abstract contract - send a prompt (+ optional file),
                 get raw text back, or raise AIServiceError.
- GeminiClient : the real Google Gemini implementation.
- MockAIClient : scripted implementation for tests / offline demos, so
                 the pipeline can run without a live API.

AIManager only ever depends on the AIClient abstraction (Dependency
Inversion), so any implementation can be substituted without changes
(Liskov Substitution). No business rules, parsing or printing here.
"""

from abc import ABC, abstractmethod
from typing import Callable, Iterable, Optional

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from config import AI_MODEL_NAME, AI_FALLBACK_MODELS, get_api_key


class AIServiceError(Exception):
    """Raised by an AIClient when the AI service cannot give a response.

    The message is always safe to show to a user - it never contains the
    API key.
    """


class AIClient(ABC):
    """Interface: anything that can turn a prompt into raw response text."""

    @abstractmethod
    def generate(self, prompt: str, file_bytes: Optional[bytes] = None,
                 mime_type: Optional[str] = None) -> str:
        """Return the model's raw text, or raise AIServiceError."""


class GeminiClient(AIClient):
    """Calls Google Gemini, falling back through a chain of models.

    A model is skipped (next one tried) only for errors where another
    model could plausibly succeed: not found/retired, rate limited, or
    server-side errors. Auth and bad-request errors stop immediately.
    """

    _UNAVAILABLE_CODES = frozenset({404, 429, 500, 502, 503, 504})
    _AUTH_CODES = frozenset({401, 403})

    def __init__(self, models: Optional[Iterable[str]] = None,
                 key_provider: Callable[[], Optional[str]] = get_api_key):
        # Primary model first, then fallbacks; duplicates removed.
        self.__models = list(dict.fromkeys(models or [AI_MODEL_NAME, *AI_FALLBACK_MODELS]))
        self.__key_provider = key_provider  # key is read lazily, never stored

    def generate(self, prompt, file_bytes=None, mime_type=None):
        api_key = self.__key_provider()
        if not api_key:
            raise AIServiceError("AI API key not configured.")

        contents = [prompt]
        if file_bytes is not None:
            if not mime_type:
                raise AIServiceError("A file was provided without a MIME type.")
            contents.append(types.Part.from_bytes(data=file_bytes, mime_type=mime_type))

        client = genai.Client(api_key=api_key)

        for model_name in self.__models:
            try:
                response = client.models.generate_content(model=model_name, contents=contents)
            except genai_errors.APIError as exc:
                if exc.code in self._AUTH_CODES:
                    raise AIServiceError(
                        "Authentication with the AI service failed. "
                        "Check that GEMINI_API_KEY is set correctly."
                    ) from None
                if self._is_model_unavailable(exc):
                    continue  # try the next model in the chain
                raise AIServiceError("The AI service rejected the request.") from None
            except Exception:
                raise AIServiceError(
                    "Could not reach the AI service due to a network or unexpected error."
                ) from None

            text = getattr(response, "text", None) if response else None
            if not text:
                raise AIServiceError("The AI service returned an empty response.")
            return text

        raise AIServiceError("The AI service is currently unavailable. Please try again later.")

    @classmethod
    def _is_model_unavailable(cls, exc) -> bool:
        return exc.code in cls._UNAVAILABLE_CODES or exc.status == "UNAVAILABLE"


class MockAIClient(AIClient):
    """Returns pre-scripted responses in order (for tests / offline use).

    Each item is either a string (returned) or an Exception instance
    (raised), so failures can be simulated too. Every prompt received is
    recorded in `calls`. When the script runs out, AIServiceError is raised.
    """

    def __init__(self, responses: Iterable = ()):
        self._responses = list(responses)
        self.calls = []

    def generate(self, prompt, file_bytes=None, mime_type=None):
        self.calls.append({"prompt": prompt, "file_bytes": file_bytes, "mime_type": mime_type})
        if not self._responses:
            raise AIServiceError("MockAIClient has no more scripted responses.")
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item
