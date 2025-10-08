"""Utility helpers to persist temporary files used by background jobs."""

from __future__ import annotations

import io
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import BinaryIO


class TemporaryObjectStorage:
    """Simple filesystem based object storage used for transient artifacts."""

    def __init__(self, base_path: str | Path | None = None) -> None:
        if base_path is None:
            base_path = Path(tempfile.gettempdir()) / "wa_cost_router"
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _prepare_target(self, prefix: str, suffix: str) -> Path:
        safe_prefix = prefix or "uploads"
        if suffix and not suffix.startswith(".") and "." not in suffix:
            safe_suffix = f".{suffix}"
        else:
            safe_suffix = suffix
        target_dir = self.base_path / safe_prefix
        target_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{uuid.uuid4()}{safe_suffix}"
        return target_dir / filename

    def store_fileobj(
        self,
        fileobj: BinaryIO,
        *,
        prefix: str = "uploads",
        suffix: str = "",
    ) -> str:
        """Persist the contents of a binary file object and return its URI."""

        target = self._prepare_target(prefix, suffix)
        try:
            fileobj.seek(0)
        except (AttributeError, io.UnsupportedOperation):
            pass

        with open(target, "wb") as destination:
            shutil.copyfileobj(fileobj, destination)

        return str(target)

    def store_bytes(
        self,
        payload: bytes,
        *,
        prefix: str = "uploads",
        suffix: str = "",
    ) -> str:
        """Persist raw bytes and return a URI pointing to the stored object."""

        target = self._prepare_target(prefix, suffix)
        with open(target, "wb") as destination:
            destination.write(payload)

        return str(target)

    def open(self, uri: str, mode: str = "rb", **kwargs):
        """Return a file handle to the stored object."""

        return open(Path(uri), mode, **kwargs)

    def read_bytes(self, uri: str) -> bytes:
        """Read all bytes stored in the provided URI."""

        return Path(uri).read_bytes()
