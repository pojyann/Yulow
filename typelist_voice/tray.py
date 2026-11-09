from __future__ import annotations

import threading
import sys
from pathlib import Path
from typing import Callable


def _resource_path(relative: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return root / relative


class TrayIcon:
    def __init__(self, show: Callable[[], None], quit_app: Callable[[], None], english: bool) -> None:
        import pystray
        from PIL import Image

        image = Image.open(_resource_path("assets/yulow-bunny-hole.png")).convert("RGBA")
        image.thumbnail((64, 64), Image.Resampling.LANCZOS)
        self.icon = pystray.Icon(
            "Yulow", image, "Yulow｜語落",
            menu=pystray.Menu(
                pystray.MenuItem("Open Yulow" if english else "開啟 Yulow",
                                 lambda icon, item: show(), default=True),
                pystray.MenuItem("Quit" if english else "結束程式",
                                 lambda icon, item: quit_app()),
            ),
        )
        threading.Thread(target=self.icon.run, daemon=True, name="yulow-tray").start()

    def stop(self) -> None:
        self.icon.stop()
