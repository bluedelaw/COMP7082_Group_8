# record_and_transcribe.py
from __future__ import annotations

import time

import config as cfg
from audio.mic import load_whisper_model, record_and_prepare_chunk
from audio.speech_recognition import transcribe_audio

def main():
    s = cfg.settings
    model, device, model_size = load_whisper_model()
    print(f"🧠 Model ready: {model_size} on {device}")

    try:
        while True:
            amp_wav = record_and_prepare_chunk(
                basename="cli",
                seconds=s.record_seconds,
                amp_factor=s.amp_factor,
            )
            text = transcribe_audio(amp_wav, model=model, device=device)
            print("🗣️ You said:", text)
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Exiting...")

if __name__ == "__main__":
    main()
