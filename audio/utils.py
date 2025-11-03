# audio/utils.py
from __future__ import annotations
import os, sys, contextlib, wave
import numpy as np

@contextlib.contextmanager
def suppress_alsa_warnings_if_linux():
    """Silence ALSA warnings on Linux; no-op elsewhere."""
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

def _peak_normalize_int16(x: np.ndarray, target_dbfs: float) -> np.ndarray:
    if x.size == 0:
        return x
    peak = int(np.max(np.abs(x)))
    if peak == 0:
        return x
    target_linear = 32767.0 * (10.0 ** (target_dbfs / 20.0))
    gain = target_linear / float(peak)
    return np.clip(x.astype(np.float32) * gain, -32768.0, 32767.0).astype(np.int16)

def write_wav_int16_mono(path: str, pcm: np.ndarray, sample_rate: int, normalize_dbfs: float | None = None) -> None:
    y = _peak_normalize_int16(pcm, normalize_dbfs) if normalize_dbfs is not None else pcm
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(y.tobytes())
