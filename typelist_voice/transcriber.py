from __future__ import annotations

import wave
from pathlib import Path
from typing import Callable


class Transcriber:
    def __init__(self, model_size: str = "small") -> None:
        self.model_size = model_size
        self.model = None

    def transcribe(self, audio_path: Path, status: Callable[[str], None]) -> tuple[str, str]:
        from faster_whisper import WhisperModel

        if self.model is None:
            status("首次載入語音模型，請稍候…")
            self.model = WhisperModel(self.model_size, device="cpu", compute_type="int8")

        segments, info = self.model.transcribe(
            str(audio_path),
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
            beam_size=5,
            condition_on_previous_text=False,
        )
        text = "".join(segment.text for segment in segments).strip()
        if not text:
            raise RuntimeError("沒有辨識到清楚的語音")
        return text, info.language


def save_wav(path: Path, frames: object, sample_rate: int = 16000) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(frames.tobytes())
