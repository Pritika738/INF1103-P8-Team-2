import re
from typing import Dict, List, Optional
from file import ExtractedFile

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class User:
    """A user, identified by a unique username."""

    def __init__(self, username: str):
        username = (username or "").strip()
        if not username:
            raise ValueError("username must not be empty.")

        self.__username = username            # identity: read-only
        self.__files: List[ExtractedFile] = []  # aggregation

    # ------------------------------------------------------------------
    # Read-only identity
    # ------------------------------------------------------------------

    @property
    def username(self) -> str:
        return self.__username

    @property
    def email(self) -> Optional[str]:
        return self.__email

    @email.setter
    def email(self, value: Optional[str]) -> None:
        if value is not None and not _EMAIL_PATTERN.match(value):
            raise ValueError("email is not a valid address.")
        self.__email = value

    # ------------------------------------------------------------------
    # Files belonging to this user
    # ------------------------------------------------------------------

    @property
    def files(self) -> List[ExtractedFile]:
        """A copy, so callers cannot modify the internal list directly."""
        return list(self.__files)

    def add_file(self, extracted_file: ExtractedFile) -> None:
        self.__files.append(extracted_file)

    def files_by_date(self) -> List[ExtractedFile]:
        """Files with a known report date, oldest first."""
        dated = [f for f in self.__files if f.report_date]
        return sorted(dated, key=lambda f: f.report_date)

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, str]:
        """Profile only (files are stored separately by the Data Manager)."""
        return {"username": self.__username}

    @classmethod
    def from_dict(cls, data: dict) -> "User":
         return cls(data.get("username"))

    def __eq__(self, other) -> bool:
        return isinstance(other, User) and other.username == self.__username

    def __hash__(self) -> int:
        return hash(self.__username)

    def __repr__(self) -> str:
        return f"User(username={self.__username!r})"
