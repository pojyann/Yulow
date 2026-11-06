"""Short, gentle cues that do not resemble Windows warning sounds."""

from __future__ import annotations

import io
import math
import struct
import threading
import wave
import winsound
from functools import lru_cache


SAMPLE_RATE = 22050
NOTES = {
    "start": ((660, 0.10), (880, 0.13)),
    "stop": ((880, 0.10), (660, 0.13)),
    "error": ((440, 0.16),),
}


@lru_cache(maxsize=3)
def _wav_bytes(kind: str) -> bytes:
    samples: list[int] = []
    for frequency, duration in NOTES[kind]:
        count = int(SAMPLE_RATE * duration)
        for index in range(count):
            position = index / count
            envelope = min(1.0, position * 12, (1 - position) * 12)
            value = 0.13 * envelope * math.sin(2 * math.pi * frequency * index / SAMPLE_RATE)
            samples.append(int(32767 * value))
        samples.extend([0] * int(SAMPLE_RATE * 0.025))
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(SAMPLE_RATE)
        audio.writeframes(struct.pack(f"<{len(samples)}h", *samples))
    return output.getvalue()


def play(kind: str) -> None:
    def run() -> None:
        try:
            winsound.PlaySound(_wav_bytes(kind), winsound.SND_MEMORY)
        except RuntimeError:
            pass

    threading.Thread(target=run, daemon=True, name=f"cue-{kind}").start()
