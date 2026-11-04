"""
ai_layer/retry.py

Retry behaviour, kept separate from AIManager (Single Responsibility).
"""

import time
from typing import Callable, Iterator


class RetryPolicy:
    """Decides how many attempts are allowed and how long to wait between them.

    The wait grows exponentially (base_delay, 2x, 4x, ...). The default
    base_delay of 0 means "retry immediately", which keeps tests fast.
    """

    def __init__(self, max_attempts: int, base_delay: float = 0.0,
                 sleeper: Callable[[float], None] = time.sleep):
        self._max_attempts = max(1, int(max_attempts))
        self._base_delay = base_delay
        self._sleeper = sleeper

    @property
    def max_attempts(self) -> int:
        return self._max_attempts

    def attempts(self) -> Iterator[int]:
        """Yield attempt numbers 1..max_attempts, pausing before each retry."""
        for attempt in range(1, self._max_attempts + 1):
            if attempt > 1 and self._base_delay > 0:
                self._sleeper(self._base_delay * 2 ** (attempt - 2))
            yield attempt
