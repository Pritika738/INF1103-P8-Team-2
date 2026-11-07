from typing import Dict, List
from file import ExtractedFile


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
    def key(self) -> str:
        """Lowercase username, matching how accounts are keyed in users.json."""
        return self.__username.lower()

    # ------------------------------------------------------------------
    # Files belonging to this user
    # ------------------------------------------------------------------

    @property
    def files(self) -> List[ExtractedFile]:
        """A copy, so callers cannot modify the internal list directly."""
        return list(self.__files)

    @property
    def file_count(self) -> int:
        """How many files this user has."""
        return len(self.__files)

    def add_file(self, extracted_file: ExtractedFile) -> None:
        """Attach a file to this user. Rejects non-files and duplicates."""
        if not isinstance(extracted_file, ExtractedFile):
            raise TypeError("add_file expects an ExtractedFile object.")
        if extracted_file in self.__files:
            raise ValueError(f"{extracted_file.source!r} has already been added.")
        self.__files.append(extracted_file)

    def remove_file(self, source: str) -> ExtractedFile:
        """Detach the file with this source and return it."""
        for index, extracted_file in enumerate(self.__files):
            if extracted_file.source == source:
                return self.__files.pop(index)
        raise ValueError(f"No file with source {source!r}.")

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

    def __eq__(self, other: object) -> bool:
        """Usernames are case-insensitive: 'Alice' and 'alice' are the same user."""
        if not isinstance(other, User):
            return NotImplemented
        return self.key == other.key

    def __hash__(self) -> int:
        return hash(self.key)

    def __repr__(self) -> str:
        return f"User(username={self.__username!r})"
