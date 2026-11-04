"""
data_layer/original_report_archive.py

The actual uploaded medical report file (PDF/image), kept byte-for-byte
as uploaded - distinct from health_records.json (the AI Manager's
extracted numbers) and from the consultation-summary PDFs (the AI
Manager's own generated output). Every original report is kept
forever; config.LATEST_REPORTS_LIMIT never applies here.
"""

import hashlib
import os
import uuid
from datetime import date as _date
from typing import List, Optional

from config import ORIGINAL_REPORTS_DIR, ORIGINAL_REPORTS_FILE

from .filenames import guess_extension
from .json_store import JsonListStore


class OriginalReportArchive:
    """Saves, lists and retrieves original uploaded medical report files."""

    def __init__(self, reports_dir: str = ORIGINAL_REPORTS_DIR,
                 metadata_file: str = ORIGINAL_REPORTS_FILE):
        self._reports_dir = reports_dir
        self.__store = JsonListStore(metadata_file)  # composition

    def save(self, file_bytes: bytes, original_filename: str, mime_type: str,
              report_date, username: str) -> Optional[dict]:
        """Save an uploaded file exactly as uploaded and record its metadata.

        If the exact same bytes have already been saved for this user
        (checked by a content hash, not by filename), the existing entry is
        reused instead of storing a second physical copy. Each stored file
        is named using a unique ID, never the original filename alone, so
        two different files that happen to share a name never collide.

        Returns the metadata dict on success, or None if saving failed.
        """
        content_hash = hashlib.sha256(file_bytes).hexdigest()

        existing = self.__store.load()
        for entry in existing:
            if entry.get("username") == username and entry.get("content_hash") == content_hash:
                return entry  # identical file already stored for this user

        try:
            os.makedirs(self._reports_dir, exist_ok=True)
        except OSError:
            return None

        report_id = uuid.uuid4().hex
        extension = os.path.splitext(original_filename)[1] or guess_extension(mime_type)
        stored_filename = f"{report_id}{extension}"
        file_path = os.path.join(self._reports_dir, stored_filename)

        try:
            with open(file_path, "wb") as f:
                f.write(file_bytes)
        except OSError:
            return None

        entry = {
            "report_id": report_id,
            "username": username,
            "report_date": report_date,
            "upload_date": _date.today().isoformat(),
            "filename": original_filename,
            "stored_filename": stored_filename,
            "mime_type": mime_type,
            "content_hash": content_hash,
        }

        existing.append(entry)
        if not self.__store.save(existing):
            return None
        return entry

    def list_for_user(self, username: str) -> List[dict]:
        """List a user's original reports, newest report date first."""
        user_entries = [e for e in self.__store.load() if e.get("username") == username]
        return sorted(user_entries, key=lambda e: e.get("report_date") or "", reverse=True)

    def read_bytes(self, stored_filename: str) -> Optional[bytes]:
        """Read back a saved file's raw bytes, or None if missing/unreadable."""
        file_path = os.path.join(self._reports_dir, os.path.basename(stored_filename))
        try:
            with open(file_path, "rb") as f:
                return f.read()
        except OSError:
            return None

    def find_by_id(self, report_id: str) -> Optional[dict]:
        """Find one original report's metadata by its report_id."""
        for entry in self.__store.load():
            if entry.get("report_id") == report_id:
                return entry
        return None
