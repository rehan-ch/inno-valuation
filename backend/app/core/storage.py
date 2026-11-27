"""Where generated files are kept (Phase 7): the PDF reports.

Files are addressed by a key such as ``reports/<organisation id>/<report id>.pdf``. Nothing
outside the app ever reads a key: downloads go through the API, which checks who is asking
first, so no file has a public address.

Development and tests keep files on this machine, under ``FILE_STORAGE_DIR``. A deployed
site needs durable object storage, chosen with the hosting (Phase 8); ``FileStorage`` is
the seam for it.
"""

import os
import re
import tempfile
from pathlib import Path
from typing import Final, Protocol

from app.core.settings import get_settings

# Lower-case segments of letters, digits, dashes and underscores, the last one with an
# extension: no "..", no leading slash, nothing a path could escape the root with.
KEY_PATTERN: Final = re.compile(r"[a-z0-9_-]+(/[a-z0-9_-]+)*\.[a-z0-9]+")


class FileStorage(Protocol):
    def put(self, key: str, data: bytes) -> None: ...

    def get(self, key: str) -> bytes:
        """The file's bytes. Raises ``FileNotFoundError`` when there is none."""
        ...

    def delete(self, key: str) -> None: ...


def check_key(key: str) -> str:
    if not KEY_PATTERN.fullmatch(key):
        raise ValueError(f"Not a storage key: {key!r}")
    return key


class LocalFileStorage:
    """Files on this machine, under ``root``. Writes are atomic: a reader sees the whole
    file or none of it."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def _path(self, key: str) -> Path:
        path = (self.root / check_key(key)).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise ValueError(f"Not a storage key: {key!r}")
        return path

    def put(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=".upload-")
        try:
            with os.fdopen(handle, "wb") as file:
                file.write(data)
            os.replace(temporary, path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


_override: FileStorage | None = None


def get_storage() -> FileStorage:
    return _override or LocalFileStorage(get_settings().file_storage_dir)


def override_storage(storage: FileStorage | None) -> None:
    """Tests keep their files in a temporary folder."""
    global _override  # noqa: PLW0603
    _override = storage
