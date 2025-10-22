import pyaudio

def list_working_input_devices() -> list[tuple[int, str]]:
    """Return only devices that can actually open a stream at 16kHz mono."""
    p = pyaudio.PyAudio()
    working = []
    try:
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info.get("maxInputChannels", 0) < 1:
                continue
            # Try opening the device
            try:
                stream = p.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=16000,
                    input=True,
                    input_device_index=i,
                    frames_per_buffer=1024,
                )
                stream.close()
                working.append((i, info["name"]))
            except Exception:
                # Skip devices that cannot open
                continue
    finally:
        p.terminate()
    return working

def get_default_input_device_index() -> int:
    """
    Choose and cache the first input device that can open a PyAudio stream.
    Auto-detects supported sample rate.
    """
    global _CACHED_DEVICE_INDEX, _CACHED_DEVICE_NAME
    if _CACHED_DEVICE_INDEX is not None:
        return _CACHED_DEVICE_INDEX

    from audio.mic import list_input_devices  # existing function

    devices = list_input_devices()
    if not devices:
        raise RuntimeError("No input devices found. Check microphone permissions.")

    p = pyaudio.PyAudio()
    for idx, name in devices:
        try:
            info = p.get_device_info_by_index(idx)
            rate = int(info.get("defaultSampleRate", 16000))
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=rate,
                input=True,
                input_device_index=idx,
                frames_per_buffer=cfg.CHUNK,
            )
            stream.close()
            _CACHED_DEVICE_INDEX = idx
            _CACHED_DEVICE_NAME = name
            print(f"🎤 Using input device [{idx}] {name} @ {rate} Hz")
            return idx
        except Exception:
            continue

    raise RuntimeError("No compatible input devices found.")

