import hashlib
import io
import tarfile

import pytest

from twinproof.artifacts import checked_bytes, source_member


def archive(*members):
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w:gz") as tf:
        for name, data, kind in members:
            info = tarfile.TarInfo(name)
            info.type = kind
            info.size = len(data) if kind == tarfile.REGTYPE else 0
            info.linkname = "../../outside"
            tf.addfile(info, io.BytesIO(data))
    return out.getvalue()


def entry(data=b"print('ok')\n"):
    return {"path": "main.py", "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def test_verified_bytes_return_without_modification():
    assert checked_bytes(b"abc", hashlib.sha256(b"abc").hexdigest(), 3) == b"abc"


@pytest.mark.parametrize("digest,size", [("0" * 64, 3), (hashlib.sha256(b"abc").hexdigest(), 2)])
def test_hash_or_size_mismatch_rejects_download(digest, size):
    with pytest.raises(ValueError):
        checked_bytes(b"abc", digest, size)


def test_selected_regular_source_ignores_cache_contents():
    blob = archive(("./main.py", b"print('ok')\n", tarfile.REGTYPE),
                   (".pytest_cache/v/cache/lastfailed", b"DO NOT READ", tarfile.REGTYPE))
    assert source_member(blob, entry()) == b"print('ok')\n"


@pytest.mark.parametrize("name,kind", [("../outside", tarfile.REGTYPE), ("/absolute", tarfile.REGTYPE),
                                      ("link", tarfile.SYMTYPE), ("link", tarfile.LNKTYPE)])
def test_unsafe_archive_members_rejected(name, kind):
    blob = archive(("main.py", b"print('ok')\n", tarfile.REGTYPE), (name, b"x", kind))
    with pytest.raises(ValueError):
        source_member(blob, entry())


def test_duplicate_normalized_source_path_rejected():
    blob = archive(("main.py", b"print('ok')\n", tarfile.REGTYPE),
                   ("./main.py", b"print('ok')\n", tarfile.REGTYPE))
    with pytest.raises(ValueError):
        source_member(blob, entry())


def test_selected_source_digest_mismatch_rejected():
    blob = archive(("main.py", b"print('bad')\n", tarfile.REGTYPE))
    with pytest.raises(ValueError):
        source_member(blob, entry())


def test_missing_selected_source_rejected():
    with pytest.raises(ValueError):
        source_member(archive(("other.py", b"x", tarfile.REGTYPE)), entry())
