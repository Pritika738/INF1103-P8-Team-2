"""
io_layer/interface.py

The terminal "channel" the IO Manager talks through.

UserInterface is the contract; ConsoleInterface is the real
implementation (input()/print()). Tests and other front-ends can supply
their own implementation without changing IOManager (Dependency
Inversion / Liskov Substitution).

These are the only places in the application where input() and print()
are allowed to appear.
"""

from abc import ABC, abstractmethod


class UserInterface(ABC):
    """Interface: read a line from the user, write a line to the user."""

    @abstractmethod
    def read(self, prompt: str) -> str:
        """Show `prompt` and return what the user typed."""

    @abstractmethod
    def write(self, message: str = "") -> None:
        """Show `message` to the user."""


class ConsoleInterface(UserInterface):
    """Standard terminal implementation."""

    def read(self, prompt: str) -> str:
        return input(prompt)

    def write(self, message: str = "") -> None:
        print(message)
