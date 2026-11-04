"""AI support package: clients, parsing, retry policy, prompts and tasks.

The orchestrating class, AIManager, lives in the top-level ai_manager.py.
(Named ai_layer to match io_layer and data_layer.)
"""

from .client import AIClient, AIServiceError, GeminiClient, MockAIClient
from .parser import ResponseParser
from .retry import RetryPolicy
from .tasks import AITask, ExtractionTask, NarrativeTask, VerificationTask

__all__ = [
    "AIClient", "AIServiceError", "GeminiClient", "MockAIClient",
    "ResponseParser", "RetryPolicy",
    "AITask", "ExtractionTask", "VerificationTask", "NarrativeTask",
]
