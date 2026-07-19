"""Small dependency-free helpers for durable artifact writes.

Every final artifact is written through a unique same-directory temporary file,
flushed, and then replaced.  Callers still own multi-file transaction policy;
these helpers guarantee that one JSON/byte artifact is never exposed half-written
and that failed writes do not leave a fixed-name temporary collision behind.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize an artifact using the repository's deterministic JSON format."""
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def write_bytes_atomic(path: Path, data: bytes) -> None:
    """Replace one regular artifact atomically, cleaning up on any failure."""
    requested = path.expanduser()
    if requested.is_symlink():
        raise OSError(f"refusing to overwrite symlink: {requested}")
    target = requested.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(target)
        temporary = None
        # Persist the directory entry when the platform supports directory fsync.
        try:
            directory_fd = os.open(target.parent, os.O_RDONLY)
        except OSError:
            directory_fd = None
        if directory_fd is not None:
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def write_json_atomic(path: Path, value: Any) -> None:
    """Serialize and atomically replace one JSON artifact."""
    write_bytes_atomic(path, canonical_json_bytes(value))


def copy_file_atomic(source: Path, destination: Path) -> None:
    """Copy a regular source file into a destination without partial output."""
    if source.is_symlink() or not source.is_file():
        raise OSError(f"source is not a regular file: {source}")
    write_bytes_atomic(destination, source.read_bytes())
