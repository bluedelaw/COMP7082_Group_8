import pyaudio

import os
import sys
import contextlib

@contextlib.contextmanager
def suppress_alsa_warnings():
    """
    Suppresses ALSA lib warnings to keep logs clean.
    """
    stderr_fileno = sys.stderr.fileno()
    with open(os.devnull, "w") as devnull:
        old_stderr = os.dup(stderr_fileno)
        os.dup2(devnull.fileno(), stderr_fileno)
        try:
            yield
        finally:
            os.dup2(old_stderr, stderr_fileno)
            os.close(old_stderr)


p = pyaudio.PyAudio()
print("Available input devices:")
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    if info.get("maxInputChannels", 0) > 0:
        print(f"[{i}] {info['name']} | Default rate: {int(info['defaultSampleRate'])} Hz")
p.terminate()
