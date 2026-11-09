import os
from datetime import datetime
from typing import List, Optional

from config import MEDICAL_PROFILE_PDF_DIR, DATABASE_FILE
from .filenames import safe_filename_component
from .sqlite_list_store import SqliteListStore

def medical_profile_pdfs_table(db_path: str = DATABASE_FILE) -> SqliteListStore:
    return SqliteListStore(
        db_path,
        "medical_profile_pdfs",
        ("username", "generated_at", "filename", "pdf_path"),
        indexes=(("username",),),
    )


class MedicalProfilePdfArchive:

    def __init__(
        self,
        pdf_dir: str = MEDICAL_PROFILE_PDF_DIR,
        metadata_store=None
    ):
        self._pdf_dir = pdf_dir
        self._store = (
            metadata_store
            if metadata_store is not None
            else medical_profile_pdfs_table()
        )

    def save(
        self,
        pdf_bytes: bytes,
        username: str
    ) -> Optional[dict]:

        try:
            os.makedirs(self._pdf_dir, exist_ok=True)
        except OSError:
            return None

        generated_at = datetime.now().isoformat(timespec="microseconds")

        filename = (
            f"medical_profile_{safe_filename_component(username)}_"
            f"{safe_filename_component(generated_at.replace(':', '-'))}.pdf"
        )

        pdf_path = os.path.join(self._pdf_dir, filename)

        try:
            with open(pdf_path, "wb") as file:
                file.write(pdf_bytes)
        except OSError:
            return None

        entry = {
            "username": username,
            "generated_at": generated_at,
            "filename": filename,
            "pdf_path": os.path.join(
                os.path.basename(os.path.normpath(self._pdf_dir)),
                filename
            ),
        }

        entries = self._store.load()
        entries.append(entry)

        if not self._store.save(entries):
            return None

        return entry

    def list_for_user(self, username: str) -> List[dict]:

        entries = [
            entry
            for entry in self._store.load()
            if entry.get("username") == username
        ]

        return sorted(
            entries,
            key=lambda entry: entry.get("generated_at") or "",
            reverse=True
        )

    def read_pdf_bytes(self, filename: str) -> Optional[bytes]:

        path = os.path.join(
            self._pdf_dir,
            os.path.basename(filename)
        )

        try:
            with open(path, "rb") as file:
                return file.read()
        except OSError:
            return None