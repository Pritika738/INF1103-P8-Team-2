"""
data_layer/consultation_archive.py

Generated consultation-summary PDFs: the file on disk plus its
metadata. Never touches health_records.json - pruning old summaries can
never delete a medical record.

ConsultationPdfArchive owns a JsonListStore for its metadata
(composition - the store has no purpose outside this archive).
"""

import os
from datetime import datetime as _datetime
from typing import List, Optional

from config import CONSULTATION_PDF_DIR, CONSULTATION_SUMMARIES_FILE, MAX_RETAINED_SUMMARY_PDFS

from .filenames import safe_filename_component
from .json_store import JsonListStore


class ConsultationPdfArchive:
    """Saves, lists and retrieves generated consultation-summary PDFs."""

    def __init__(self, pdf_dir: str = CONSULTATION_PDF_DIR,
                 summaries_file: str = CONSULTATION_SUMMARIES_FILE,
                 max_retained: Optional[int] = MAX_RETAINED_SUMMARY_PDFS):
        self._pdf_dir = pdf_dir
        self._max_retained = max_retained
        self.__store = JsonListStore(summaries_file)  # composition

    def save(self, pdf_bytes: bytes, report_date, username: str,
              source_record_id=None) -> Optional[dict]:
        """Save a generated PDF and record its metadata.

        Always writes a new entry - it never checks for or skips duplicates
        itself. Callers that need "don't save the same summary twice"
        behaviour should call find_by_source() first and only call this when
        it returns None.

        Returns the new metadata dict on success, or None if saving failed.
        """
        try:
            os.makedirs(self._pdf_dir, exist_ok=True)
        except OSError:
            return None

        # Microsecond precision: several summaries can genuinely be
        # generated within the same second, and this value is also used
        # to order/prune old ones, so it must be unique per save.
        generated_at = _datetime.now().isoformat(timespec="microseconds")
        filename = (
            f"consultation_{safe_filename_component(username)}_"
            f"{safe_filename_component(report_date)}_"
            f"{safe_filename_component(generated_at.replace(':', '-'))}.pdf"
        )
        pdf_path = os.path.join(self._pdf_dir, filename)

        try:
            with open(pdf_path, "wb") as f:
                f.write(pdf_bytes)
        except OSError:
            return None

        entry = {
            "username": username,
            "source_record_id": source_record_id,
            "report_date": report_date,
            "generated_at": generated_at,
            "filename": filename,
            # Relative to the PDFs directory, not an absolute host path,
            # since that directory can live somewhere different inside a
            # Docker container than on the host.
            "pdf_path": os.path.join(os.path.basename(os.path.normpath(self._pdf_dir)), filename),
        }

        summaries = self.__store.load()
        summaries.append(entry)
        summaries = self._prune(summaries, username)

        if not self.__store.save(summaries):
            return None
        return entry

    def _prune(self, summaries: list, username: str) -> list:
        """Delete the oldest PDFs for `username` beyond max_retained (None = keep all)."""
        if self._max_retained is None:
            return summaries

        other_entries = [s for s in summaries if s.get("username") != username]
        user_entries = sorted(
            (s for s in summaries if s.get("username") == username),
            key=lambda s: s.get("generated_at") or "",
        )
        if len(user_entries) > self._max_retained:
            for old in user_entries[:-self._max_retained]:
                try:
                    os.remove(os.path.join(self._pdf_dir, old["filename"]))
                except OSError:
                    pass
            user_entries = user_entries[-self._max_retained:]
        return other_entries + user_entries

    def find_by_source(self, username: str, source_record_id) -> Optional[dict]:
        """Find a previously saved summary generated from this exact health
        record, if one exists - the idempotency check behind "don't save the
        same summary twice".

        If `source_record_id` is falsy, always returns None - there is
        nothing reliable to match on.
        """
        if not source_record_id:
            return None
        for entry in self.__store.load():
            if entry.get("username") == username and entry.get("source_record_id") == source_record_id:
                return entry
        return None

    def list_for_user(self, username: str) -> List[dict]:
        """List a user's summaries, newest generated first."""
        user_entries = [s for s in self.__store.load() if s.get("username") == username]
        return sorted(user_entries, key=lambda s: s.get("generated_at") or "", reverse=True)

    def read_pdf_bytes(self, filename: str) -> Optional[bytes]:
        """Read back a saved PDF's raw bytes, or None if missing/unreadable."""
        # basename() strips any directory components so a stray "../" in a
        # filename can never escape pdf_dir.
        pdf_path = os.path.join(self._pdf_dir, os.path.basename(filename))
        try:
            with open(pdf_path, "rb") as f:
                return f.read()
        except OSError:
            return None
