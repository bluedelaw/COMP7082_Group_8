# audio/utils.py
from __future__ import annotations
import os, sys, contextlib

@contextlib.contextmanager
def suppress_alsa_warnings_if_linux():
    if not sys.platform.startswith("linux"):
        yield
        return
    stderr_fileno = sys.stderr.fileno()
    with open(os.devnull, "w") as devnull:
        old_stderr = os.dup(stderr_fileno)
        try:
            os.dup2(devnull.fileno(), stderr_fileno)
            yield
        finally:
            os.dup2(old_stderr, stderr_fileno)
            os.close(old_stderr)
