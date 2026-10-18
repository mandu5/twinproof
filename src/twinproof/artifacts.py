"""Read exactly pinned public artifacts without extracting an archive tree."""

import hashlib
import io
from pathlib import PurePosixPath
import tarfile


def checked_bytes(data: bytes, digest: str, size: int) -> bytes:
    if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
        raise ValueError("artifact size or SHA-256 mismatch")
    return data


def _path(name: str) -> str:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name:
        raise ValueError("unsafe archive path")
    return str(path)


def source_member(archive: bytes, entry: dict) -> bytes:
    """Return one verified regular member; never read unselected member bodies."""
    selected = _path(entry["path"])
    if entry["bytes"] > 8 * 1024 * 1024:
        raise ValueError("selected source too large")
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tf:
        names = set()
        found = None
        total = 0
        for member in tf:
            name = _path(member.name)
            if name in names:
                raise ValueError("duplicate archive path")
            names.add(name)
            total += member.size
            if len(names) > 10000 or total > 8 * 1024 * 1024:
                raise ValueError("archive exceeds unpacked metadata limits")
            if not (member.isfile() or member.isdir()):
                raise ValueError("archive contains non-regular member")
            if name == selected:
                if not member.isfile() or member.size != entry["bytes"]:
                    raise ValueError("selected source is not the expected regular file")
                found = member
        if found is None:
            raise ValueError("selected source missing")
        stream = tf.extractfile(found)
        if stream is None:
            raise ValueError("selected source unreadable")
        return checked_bytes(stream.read(entry["bytes"] + 1), entry["sha256"], entry["bytes"])
