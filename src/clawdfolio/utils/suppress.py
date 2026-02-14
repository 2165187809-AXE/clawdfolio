"""Shared I/O suppression utilities for broker SDKs."""

from __future__ import annotations

import os
from contextlib import contextmanager


@contextmanager
def suppress_stdio():
    """Suppress stdout/stderr from native SDKs.

    Some broker SDKs (Longport, Futu) emit noisy log output to the
    file-descriptor level.  This context manager redirects fd 1 and fd 2
    to ``/dev/null`` and restores them on exit.
    """
    devnull = os.open(os.devnull, os.O_WRONLY)
    saved_out = os.dup(1)
    saved_err = os.dup(2)
    try:
        os.dup2(devnull, 1)
        os.dup2(devnull, 2)
        yield
    finally:
        try:
            os.dup2(saved_out, 1)
            os.dup2(saved_err, 2)
        finally:
            os.close(saved_out)
            os.close(saved_err)
            os.close(devnull)
