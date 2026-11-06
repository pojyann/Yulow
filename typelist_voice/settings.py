from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


APP_DIR = Path.home() / "AppData" / "Local" / "TypeListVoice"
SETTINGS_FILE = APP_DIR / "settings.json"


@dataclass
class Settings:
    model_size: str = "small"
    traditional_chinese: bool = True
    auto_paste: bool = True
    sound_cues: bool = True
    hotkey: str = "Right Alt"
    microphone: int | None = None
    interface_language: str = "繁體中文"
    theme: str = "跟隨 Windows"
    grammar_mode: str = "local_ai"
    grammar_model: str = "qwen3:4b"
    grammar_endpoint: str = "http://127.0.0.1:11434/api/chat"
    grammar_setup_prompted: bool = False
    keep_history_days: int = 30

    @classmethod
    def load(cls) -> "Settings":
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            valid = {key: value for key, value in data.items() if key in cls.__annotations__}
            if valid.get("theme") == "系統":
                valid["theme"] = "跟隨 Windows"
            return cls(**valid)
        except (OSError, ValueError, TypeError):
            return cls()

    def save(self) -> None:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8"
        )
