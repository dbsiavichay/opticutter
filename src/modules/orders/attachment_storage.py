"""Local-disk storage for order attachments (anexos).

A deliberately thin filesystem layer behind a small interface (build_key / save /
open_stream / remove) so the backend can later be swapped for object storage
(MinIO/S3) without touching the service or the router. Only the bytes live here;
the metadata row lives in Postgres (``OrderAttachmentModel``).

The on-disk name is a random ``uuid4`` (never the client-supplied filename), which
avoids collisions and path-traversal entirely.
"""

import uuid
from pathlib import Path
from typing import BinaryIO

from src.shared.config import config

# Extension used for the on-disk name, keyed by the (already validated) content type.
_EXTENSIONS = {
    "application/pdf": "pdf",
    "image/png": "png",
    "image/jpeg": "jpg",
}


def _base_dir() -> Path:
    return Path(config.ATTACHMENTS_DIR)


def build_key(order_id: int, content_type: str) -> str:
    """Builds a collision-free relative key ``{order_id}/{uuid}.{ext}``."""
    ext = _EXTENSIONS.get(content_type, "bin")
    return f"{order_id}/{uuid.uuid4().hex}.{ext}"


def save(stored_key: str, data: bytes) -> None:
    """Writes ``data`` at ``stored_key`` under the attachments dir (creates parents)."""
    path = _base_dir() / stored_key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def read(stored_key: str) -> bytes:
    """Reads the whole stored file into memory (used by the consolidated PDF merge)."""
    return (_base_dir() / stored_key).read_bytes()


def open_stream(stored_key: str) -> BinaryIO:
    """Opens the stored file for reading (binary), for streaming downloads."""
    return (_base_dir() / stored_key).open("rb")


def remove(stored_key: str) -> None:
    """Deletes the stored file; a missing file is not an error (idempotent)."""
    (_base_dir() / stored_key).unlink(missing_ok=True)
