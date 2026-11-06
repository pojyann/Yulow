from __future__ import annotations

import tkinter as tk
from typing import Callable


class RoundedButton(tk.Canvas):
    def __init__(self, master, text: str, command: Callable[[], None],
                 bg: str, fg: str = "#FFFFFF", width: int = 112, height: int = 42,
                 radius: int = 12, font=None, align: str = "center") -> None:
        super().__init__(master, width=width, height=height, bg=master.cget("bg"),
                         highlightthickness=0, borderwidth=0, cursor="hand2")
        self.command = command
        self.fill = bg
        self.color = fg
        self.radius = radius
        self.label = text
        self.label_font = font or ("Microsoft JhengHei UI", 10, "bold")
        self.align = align
        self.disabled = False
        self.bind("<Button-1>", lambda event: None if self.disabled else self.command())
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        w, h, r = int(self.cget("width")), int(self.cget("height")), self.radius
        self.create_arc(0, 0, 2*r, 2*r, start=90, extent=90, fill=self.fill, outline=self.fill)
        self.create_arc(w-2*r, 0, w, 2*r, start=0, extent=90, fill=self.fill, outline=self.fill)
        self.create_arc(0, h-2*r, 2*r, h, start=180, extent=90, fill=self.fill, outline=self.fill)
        self.create_arc(w-2*r, h-2*r, w, h, start=270, extent=90, fill=self.fill, outline=self.fill)
        self.create_rectangle(r, 0, w-r, h, fill=self.fill, outline=self.fill)
        self.create_rectangle(0, r, w, h-r, fill=self.fill, outline=self.fill)
        self.create_text(17 if self.align == "left" else w/2, h/2, text=self.label,
                         fill=self.color, font=self.label_font,
                         anchor="w" if self.align == "left" else "center")

    def set_style(self, text: str, bg: str, disabled: bool = False) -> None:
        self.label = text
        self.fill = bg
        self.disabled = disabled
        self._draw()
