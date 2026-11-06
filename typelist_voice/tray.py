from __future__ import annotations

import threading
from typing import Callable


class TrayIcon:
    def __init__(self, show: Callable[[], None], quit_app: Callable[[], None], english: bool) -> None:
        import pystray
        from PIL import Image, ImageDraw

        image = Image.new("RGBA", (64, 64), "#20272C")
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((11, 11, 53, 53), radius=13, fill="#47A98F")
        draw.ellipse((26, 19, 38, 37), fill="white")
        draw.arc((21, 22, 43, 45), 0, 180, fill="white", width=3)
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
