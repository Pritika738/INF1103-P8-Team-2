"""
io_layer/menu.py

A text menu as data: a title plus a list of options.
"""

from dataclasses import dataclass
from typing import List, Sequence


@dataclass(frozen=True)
class MenuOption:
    key: str
    label: str


class Menu:
    """A titled list of options that can render itself as text."""

    def __init__(self, title: str, options: Sequence[MenuOption]):
        self.__title = title
        self.__options = list(options)

    @property
    def keys(self) -> List[str]:
        return [option.key for option in self.__options]

    def render(self) -> str:
        lines = [f"\n===== {self.__title} ====="]
        lines += [f"{option.key}. {option.label}" for option in self.__options]
        return "\n".join(lines)

    @classmethod
    def main_menu(cls) -> "Menu":
        return cls("Health History & Consultation Prep", [
            MenuOption("1", "Add Health Record"),
            MenuOption("2", "View Health History"),
            MenuOption("3", "Analyse Health Records"),
            MenuOption("4", "Generate Consultation Report"),
            MenuOption("5", "Exit"),
        ])
