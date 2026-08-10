"""Crash-safe persistence helpers.

On an air-gapped single-server appliance a plain ``open(path,"w")`` /
``Path.write_text`` is not crash-safe: if the process is killed or the box
loses power mid-write, the shared config/token/layout file is left truncated or
half-written, and the feature that depends on it breaks for every user. These
helpers write to a temp file in the same directory and ``os.replace`` it into
place (an atomic rename on POSIX), so a reader always sees either the old file
or the complete new one — never a partial one.
"""
from __future__ import annotations

import asyncio
import functools
import os
import tempfile
from pathlib import Path
from typing import Any, Callable, Optional, Union

_PathLike = Union[str, os.PathLike]


async def run_in_thread(fn: Callable[..., Any], *args: Any) -> Any:
    """Offload a blocking call to the default thread pool so it doesn't stall
    the event loop.

    Uses ``loop.run_in_executor`` (Python 3.7+) rather than ``asyncio.to_thread``
    (3.9+): the appliance targets CentOS 7 where the available Python can be
    older than 3.9.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, functools.partial(fn, *args))


def atomic_write_text(
    path: _PathLike, data: str, *, encoding: str = "utf-8", mode: int = 0o644
) -> None:
    """Atomically write ``data`` to ``path`` (temp file + fsync + os.replace).

    ``mode`` sets the final file permission bits — pass ``0o600`` for files that
    hold secrets (server passwords, tokens). The parent directory is created if
    missing. On any error the temp file is cleaned up and the original is left
    untouched.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=f".{p.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding=encoding) as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, p)  # atomic within the same filesystem
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def restrict_mode(path: _PathLike, mode: int = 0o600) -> None:
    """Best-effort chmod for an already-written file (e.g. an append-only log
    that holds sensitive lines). Never raises."""
    try:
        os.chmod(path, mode)
    except OSError:
        pass
