"""Local-disk spool for rendered print payloads (TSPL labels, consolidated PDFs).

A deliberately thin filesystem layer behind a small interface (build_key / save /
read / open_stream / remove), mirroring ``orders.attachment_storage`` so the
backend can later be swapped for object storage without touching the service.
Only the bytes live here; the ``PrintJobModel`` row (metadata + status) lives in
Postgres. The on-disk name is a random ``uuid4`` (never client input), which
avoids collisions and path traversal entirely.
"""

import uuid
from pathlib import Path
from typing import BinaryIO

from src.shared.config import config

# Extension used for the on-disk name, keyed by the payload format.
_EXTENSIONS = {"tspl": "tspl", "pdf": "pdf"}


def _base_dir() -> Path:
    return Path(config.PRINT_SPOOL_DIR)


def build_key(branch_id: int, payload_format: str) -> str:
    """Builds a collision-free relative key ``{branch_id}/{uuid}.{ext}``."""
    ext = _EXTENSIONS.get(payload_format, "bin")
    return f"{branch_id}/{uuid.uuid4().hex}.{ext}"


def save(stored_key: str, data: bytes) -> None:
    """Writes ``data`` at ``stored_key`` under the spool dir (creates parents)."""
    path = _base_dir() / stored_key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def read(stored_key: str) -> bytes:
    """Reads the whole spooled payload into memory."""
    return (_base_dir() / stored_key).read_bytes()


def open_stream(stored_key: str) -> BinaryIO:
    """Opens the spooled payload for reading (binary), for streaming to the agent."""
    return (_base_dir() / stored_key).open("rb")


def remove(stored_key: str) -> None:
    """Deletes the spooled payload; a missing file is not an error (idempotent)."""
    (_base_dir() / stored_key).unlink(missing_ok=True)
