from __future__ import annotations

import queue
import sys
import tempfile
import threading
import webbrowser
import math
from pathlib import Path
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox, ttk
import winreg

import numpy as np

from .grammar import (
    GrammarServiceUnavailable,
    correct_with_ollama,
    ollama_is_ready,
    polish_punctuation,
)
from .settings import Settings
from .sounds import play
from .storage import Storage
from .transcriber import Transcriber, save_wav
from .tray import TrayIcon
from .windows import RightAltHook, focus_window, foreground_window, paste, round_window, style_title_bar, undo
from .widgets import RoundedButton


APP_NAME = "Yulow｜語落"
SAMPLE_RATE = 16000


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.settings = Settings.load()
        self.storage = Storage()
        self.storage.purge_old(self.settings.keep_history_days)
        self.transcriber = Transcriber(self.settings.model_size)
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.recording = False
        self.processing = False
        self.frames: list[np.ndarray] = []
        self.stream = None
        self.target_hwnd = 0
        self.last_text = ""
        self.last_language: str | None = None
        self.hidden_to_tray = False
        self.overlay: tk.Toplevel | None = None
        self.overlay_generation = 0
        self.overlay_loading = False
        self.overlay_step = 0

        self.status = tk.StringVar(value="按一下右 Alt 開始錄音")
        self.preview = tk.StringVar(value="說話之後，文字會出現在這裡。")
        self.raw_preview = tk.StringVar(value="—")
        self.grammar_status = tk.StringVar(value="等待語音辨識")
        self.grammar_result = tk.StringVar(value="—")
        self.wave_step = 0
        self._configure_window()
        self._build_ui()

        self.hook = RightAltHook(
            lambda: self.events.put(("toggle", None)),
            lambda error: self.events.put(("status", error)),
            self.settings.hotkey,
        )
        self.hook.start()
        self.tray = TrayIcon(
            lambda: self.events.put(("show_main", None)),
            lambda: self.events.put(("quit", None)),
            self.settings.interface_language == "English",
        )
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<Unmap>", self._on_unmap)
        self.root.after(50, self._poll_events)
        self.root.after(1200, self._offer_grammar_setup)

    def _on_unmap(self, event: tk.Event) -> None:
        if event.widget is self.root and self.root.state() == "iconic":
            self.root.after(60, self._hide_to_tray)

    def _hide_to_tray(self) -> None:
        if self.root.state() == "iconic":
            self.root.withdraw()
            self.hidden_to_tray = True

    def _show_main(self) -> None:
        self.hidden_to_tray = False
        self._hide_overlay()
        self.root.deiconify()
        self.root.lift()

    def _offer_grammar_setup(self) -> None:
        """Offer, but never force, the optional local AI installation."""
        if self.settings.grammar_setup_prompted or self.settings.grammar_mode != "local_ai":
            return

        def check() -> None:
            ready = ollama_is_ready(self.settings.grammar_model, self.settings.grammar_endpoint)
            self.events.put(("grammar_setup_check", ready))

        threading.Thread(target=check, daemon=True).start()

    def _show_grammar_setup(self, first_run: bool = False) -> None:
        if first_run:
            self.settings.grammar_setup_prompted = True
            self.settings.save()
        dialog = tk.Toplevel(self.root)
        dialog.title(" ")
        dialog.configure(bg=self.card)
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.geometry("500x340")
        dialog.after(0, lambda: style_title_bar(dialog, self.dark_theme, self.card))
        tk.Label(dialog, text=self._t("啟用 AI 文法校正", "Enable AI grammar correction"),
                 bg=self.card, fg=self.fg, font=("Microsoft JhengHei UI", 18, "bold")).pack(
                     anchor="w", padx=28, pady=(28, 10)
                 )
        guide = self._t(
            "這是可選功能。安裝一次本機 AI 後，中文、英文與日文都能校正文法；不需要 API，也沒有每日額度。\n\n"
            "1. 安裝 Ollama 桌面版\n"
            "2. 在 Ollama 裡下載推薦模型：qwen3:4b\n"
            "3. 回到語落開始使用\n\n"
            "模型約需數 GB 空間，校正時會使用你的電腦效能。",
            "This optional feature corrects Chinese, English, and Japanese locally. It needs no API key or daily quota.\n\n"
            "1. Install the Ollama desktop app\n"
            "2. Download the recommended model: qwen3:4b\n"
            "3. Return to Yulow and start using it\n\n"
            "The model uses several GB of disk space and your computer's processing power."
        )
        tk.Label(dialog, text=guide, bg=self.card, fg=self.muted, justify="left", anchor="nw",
                 wraplength=440, font=("Microsoft JhengHei UI", 10)).pack(
                     fill="both", expand=True, padx=28
                 )
        actions = tk.Frame(dialog, bg=self.card)
        actions.pack(fill="x", padx=28, pady=(10, 24))
        RoundedButton(actions, text=self._t("開啟 Ollama 官方下載頁", "Open Ollama download page"),
                      command=lambda: webbrowser.open("https://ollama.com/download/windows"),
                      bg=self.accent, width=210, height=40, radius=12).pack(side="left")
        RoundedButton(actions, text=self._t("稍後再說", "Maybe later"), command=dialog.destroy,
                      bg=self.border, fg=self.fg, width=110, height=40, radius=12).pack(side="right")

    def _show_overlay(self, message: str, color: str, loading: bool = False) -> None:
        if not self.hidden_to_tray:
            return
        self.overlay_generation += 1
        if self.overlay is None or not self.overlay.winfo_exists():
            self.overlay = tk.Toplevel(self.root)
            self.overlay.overrideredirect(True)
            self.overlay.attributes("-topmost", True)
            self.overlay.attributes("-alpha", 0.90)
            self.overlay.configure(bg="#20272C")
            self.overlay_canvas = tk.Canvas(self.overlay, bg="#20272C", highlightthickness=0,
                                            borderwidth=0)
            self.overlay_canvas.pack(fill="both", expand=True)
        self.overlay_message = message if len(message) <= 18 else message[:17] + "…"
        self.overlay_color = color
        self.overlay_loading = loading
        self._render_overlay()
        if loading:
            self._animate_overlay()

    def _render_overlay(self) -> None:
        if self.overlay is None or not self.overlay.winfo_exists():
            return
        font = tkfont.Font(family="Microsoft JhengHei UI", size=10)
        text_width = font.measure(self.overlay_message)
        width = max(142, min(260, text_width + 38))
        height = 58 if self.overlay_loading else 42
        x = (self.root.winfo_screenwidth() - width) // 2
        y = self.root.winfo_screenheight() - height - 72
        self.overlay.geometry(f"{width}x{height}+{x}+{y}")
        round_window(self.overlay, width, height, 13)
        canvas = self.overlay_canvas
        canvas.configure(width=width, height=height)
        canvas.delete("all")
        canvas.create_text(width / 2, 21 if self.overlay_loading else height / 2,
                           text=self.overlay_message, fill=self.overlay_color,
                           font=font, anchor="center")
        if self.overlay_loading:
            total, gap = 5, 5
            bar_width = min(78, width - 38)
            segment = (bar_width - (total - 1) * gap) / total
            left_start = (width - bar_width) / 2
            for index in range(total):
                active = index == self.overlay_step % total
                fill = "#8DDFC1" if active else "#3A4950"
                left = left_start + index * (segment + gap)
                canvas.create_rectangle(left, 42, left + segment, 45, fill=fill, outline=fill)

    def _hide_overlay(self) -> None:
        self.overlay_generation += 1
        self.overlay_loading = False
        if self.overlay is not None and self.overlay.winfo_exists():
            self.overlay.destroy()
        self.overlay = None

    def _hide_overlay_later(self, delay_ms: int) -> None:
        generation = self.overlay_generation
        self.root.after(delay_ms, lambda: self._hide_overlay()
                        if generation == self.overlay_generation else None)

    def _animate_overlay(self) -> None:
        if (not self.overlay_loading or self.overlay is None or
                not self.overlay.winfo_exists()):
            return
        self._render_overlay()
        self.overlay_step += 1
        self.root.after(170, self._animate_overlay)

    def _configure_window(self) -> None:
        self._set_palette()
        self.root.title(" ")
        self.root.geometry("1000x720+40+80")
        self.root.minsize(820, 600)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=self.bg)
        self.root.after(0, self._style_title_bar)

    def _style_title_bar(self) -> None:
        try:
            style_title_bar(self.root, self.dark_theme, self.bg)
        except (AttributeError, OSError):
            pass

    def _set_palette(self) -> None:
        dark = self.settings.theme == "深色"
        if self.settings.theme in {"系統", "跟隨 Windows"}:
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
                    dark = winreg.QueryValueEx(key, "AppsUseLightTheme")[0] == 0
            except OSError:
                dark = False
        self.bg, self.card, self.fg, self.muted, self.border, self.accent = (
            ("#14191D", "#20272C", "#F4F7F6", "#ADB9B7", "#344149", "#47A98F")
            if dark else
            ("#F5F3EF", "#FFFFFF", "#17202B", "#687681", "#E5E3DE", "#287967")
        )
        self.dark_theme = dark

    def _t(self, zh: str, en: str) -> str:
        return en if self.settings.interface_language == "English" else zh

    def _build_ui(self) -> None:
        shell = tk.Frame(self.root, bg=self.bg)
        shell.pack(fill="both", expand=True)
        sidebar = tk.Frame(shell, bg=self.card, width=200, highlightbackground=self.border, highlightthickness=1)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        tk.Label(sidebar, text="Yulow", bg=self.card, fg=self.fg,
                 font=("Segoe UI", 21, "bold"), anchor="w").pack(fill="x", padx=22, pady=(25, 4))
        tk.Label(sidebar, text="語落 · Voice to text", bg=self.card, fg=self.muted,
                 font=("Microsoft JhengHei UI", 9), anchor="w").pack(fill="x", padx=22, pady=(0, 22))
        self.nav_buttons = {}
        for page, zh, en, icon in [
            ("home", "首頁", "Home", "⌂"),
            ("history", "歷史記錄", "History", "◷"),
            ("dictionary", "字典", "Dictionary", "▤"),
        ]:
            button = RoundedButton(sidebar, text=f"{icon}   {self._t(zh, en)}",
                                   command=lambda p=page: self._show_page(p), bg=self.card,
                                   fg=self.fg, width=174, height=45, radius=10,
                                   align="left", font=("Microsoft JhengHei UI", 11))
            button.pack(fill="x", padx=12, pady=2)
            self.nav_buttons[page] = button
        tk.Frame(sidebar, bg=self.card).pack(fill="both", expand=True)
        settings_button = RoundedButton(sidebar, text=self._t("⚙   設定", "⚙   Settings"),
                                        command=self.show_settings, bg=self.card, fg=self.fg,
                                        width=174, height=45, radius=10, align="left",
                                        font=("Microsoft JhengHei UI", 11))
        settings_button.pack(fill="x", padx=12, pady=(0, 20))
        self.nav_buttons["settings"] = settings_button

        right = tk.Frame(shell, bg=self.bg)
        right.pack(side="left", fill="both", expand=True)
        self.content = tk.Frame(right, bg=self.bg)
        self.content.pack(fill="both", expand=True, padx=30, pady=(25, 8))
        footer = tk.Frame(right, bg=self.bg)
        footer.pack(fill="x", padx=30, pady=(0, 22))
        self.footer = footer
        self.settings_save_button = None
        tk.Label(footer, textvariable=self.status, bg=self.bg, fg=self.accent,
                 anchor="w", font=("Microsoft JhengHei UI", 10)).pack(side="left", fill="x", expand=True)
        self.mic_button = RoundedButton(footer, text=self._t("●  錄音", "●  Record"),
                                        command=self.toggle, bg=self.accent,
                                        width=112, height=44, radius=13)
        self.mic_button.pack(side="right")
        self._show_page("home")
        self.root.bind("<Configure>", self._resize_preview)

    def _resize_preview(self, event: tk.Event) -> None:
        if event.widget is self.root and hasattr(self, "preview_label") and self.preview_label.winfo_exists():
            self.preview_label.configure(wraplength=max(350, event.width - 310))

    def _show_page(self, page: str) -> None:
        for child in self.content.winfo_children():
            child.destroy()
        self.current_page = page
        if self.settings_save_button is not None:
            self.settings_save_button.destroy()
            self.settings_save_button = None
        if page == "settings":
            self.mic_button.pack_forget()
        elif not self.mic_button.winfo_manager():
            self.mic_button.pack(side="right")
        for name, button in self.nav_buttons.items():
            button.set_style(button.label, self.border if name == page else self.card)
        if page == "home":
            self._show_home()
        elif page == "settings":
            self._render_settings()
        else:
            self._show_list_page(page)

    def _show_home(self) -> None:
        headline = tk.Frame(self.content, bg=self.bg)
        headline.pack(fill="x", pady=(0, 18))
        tk.Label(headline, text=self._t("開口說，文字就到了。", "Speak. Your words appear."),
                 bg=self.bg, fg=self.fg, font=("Microsoft JhengHei UI", 25, "bold"),
                 anchor="w").pack(side="left")
        self.recording_indicator = tk.Label(
            headline, text=self._t("●  等待錄音", "●  Ready"), bg=self.card, fg=self.muted,
            font=("Microsoft JhengHei UI", 10, "bold"), padx=12, pady=7
        )
        self.recording_indicator.pack(side="right")
        stats = self.storage.usage_stats()
        metrics = tk.Frame(self.content, bg=self.bg)
        metrics.pack(fill="x", pady=(0, 18))
        for value, label in [
            (stats["today"], self._t("今天口述字數", "Words today")),
            (stats["week"], self._t("本週口述字數", "Words this week")),
            (stats["today"], self._t("今天少打字數", "Keystrokes saved today")),
        ]:
            card = tk.Frame(metrics, bg=self.card, highlightbackground=self.border, highlightthickness=1)
            card.pack(side="left", fill="both", expand=True, padx=(0, 10))
            tk.Label(card, text=f"{value:,}", bg=self.card, fg=self.fg,
                     font=("Segoe UI", 22, "bold"), anchor="w").pack(fill="x", padx=17, pady=(14, 0))
            tk.Label(card, text=label, bg=self.card, fg=self.muted,
                     font=("Microsoft JhengHei UI", 10), anchor="w").pack(fill="x", padx=17, pady=(0, 14))
        card = tk.Frame(self.content, bg=self.card, highlightbackground=self.border, highlightthickness=1)
        card.pack(fill="both", expand=True)
        transcript_header = tk.Frame(card, bg=self.card)
        transcript_header.pack(fill="x", padx=20, pady=(18, 0))
        tk.Label(transcript_header, text=self._t("最近一次辨識", "LATEST TRANSCRIPT"), bg=self.card,
                 fg=self.muted, anchor="w", font=("Microsoft JhengHei UI", 10, "bold")).pack(side="left")
        self.transcript_state = tk.Label(transcript_header, text=self._t("準備就緒", "Ready"), bg=self.card,
                                         fg=self.muted, font=("Microsoft JhengHei UI", 10))
        self.transcript_state.pack(side="right")
        self.preview_label = tk.Label(card, textvariable=self.preview, bg=self.card, fg=self.fg,
                                      font=("Microsoft JhengHei UI", 16), wraplength=620,
                                      justify="left", anchor="nw", padx=20, pady=11)
        self.preview_label.pack(fill="x", pady=(3, 3))
        self.waveform_canvas = tk.Canvas(card, height=42, bg=self.card, highlightthickness=0, borderwidth=0)
        self.waveform_canvas.pack(fill="x", padx=24, pady=(0, 8))
        self._animate_home_waveform()
        grammar_card = tk.Frame(card, bg=self.bg, highlightbackground=self.border, highlightthickness=1)
        grammar_card.pack(fill="x", padx=20, pady=(2, 10))
        grammar_header = tk.Frame(grammar_card, bg=self.bg)
        grammar_header.pack(fill="x", padx=13, pady=(10, 5))
        tk.Label(grammar_header, text=self._t("AI 文法校正", "AI GRAMMAR CORRECTION"), bg=self.bg,
                 fg=self.accent, font=("Microsoft JhengHei UI", 10, "bold")).pack(side="left")
        self.grammar_status_label = tk.Label(grammar_header, textvariable=self.grammar_status, bg=self.bg,
                                              fg=self.muted, font=("Microsoft JhengHei UI", 9, "bold"))
        self.grammar_status_label.pack(side="right")
        self._grammar_line(grammar_card, self._t("原始辨識", "Original"), self.raw_preview, self.muted)
        self._grammar_line(grammar_card, self._t("校正結果", "Corrected"), self.grammar_result, self.accent)
        actions = tk.Frame(card, bg=self.card)
        actions.pack(fill="x", padx=18, pady=(0, 14))
        for label, command in [(self._t("↶  復原", "↶  Undo"), self.undo_last),
                               (self._t("☆  收藏", "☆  Save phrase"), self.favorite_last)]:
            tk.Button(actions, text=label, command=command, bg=self.card, fg=self.accent,
                      relief="flat", padx=8, pady=6).pack(side="left", padx=(0, 8))

    def _grammar_line(self, parent: tk.Frame, label: str, value: tk.StringVar, color: str) -> None:
        row = tk.Frame(parent, bg=self.bg)
        row.pack(fill="x", padx=13, pady=3)
        tk.Label(row, text=label, bg=self.bg, fg=self.muted, width=8, anchor="w",
                 font=("Microsoft JhengHei UI", 9)).pack(side="left")
        tk.Label(row, textvariable=value, bg="#1A2227" if self.dark_theme else "#F0EFEB", fg=color,
                 anchor="w", justify="left", padx=10, pady=5,
                 font=("Microsoft JhengHei UI", 10)).pack(side="left", fill="x", expand=True)

    def _animate_home_waveform(self) -> None:
        canvas = getattr(self, "waveform_canvas", None)
        if canvas is None or not canvas.winfo_exists():
            return
        width = max(canvas.winfo_width(), 420)
        height = 42
        canvas.delete("all")
        bars, gap = 48, 4
        bar_width = max(2, (width - (bars - 1) * gap) / bars)
        for index in range(bars):
            motion = math.sin((index * 0.73) + self.wave_step * 0.32)
            amplitude = 4 + (abs(motion) * (13 if self.recording else 4))
            center = height / 2
            x = index * (bar_width + gap)
            color = self.accent if self.recording else self.border
            canvas.create_rectangle(x, center - amplitude, x + bar_width, center + amplitude,
                                    fill=color, outline=color)
        self.wave_step += 1
        self.root.after(100, self._animate_home_waveform)

    def _set_grammar_card(self, source: str, result: str, state: str, success: bool) -> None:
        self.raw_preview.set(source or "—")
        self.grammar_result.set(result or "—")
        self.grammar_status.set(state)
        if hasattr(self, "grammar_status_label") and self.grammar_status_label.winfo_exists():
            self.grammar_status_label.configure(fg=self.accent if success else self.muted)

    def _show_list_page(self, page: str) -> None:
        is_history = page == "history"
        title = self._t("歷史記錄" if is_history else "字典", "History" if is_history else "Dictionary")
        tk.Label(self.content, text=title, bg=self.bg, fg=self.fg,
                 font=("Microsoft JhengHei UI", 23, "bold"), anchor="w").pack(fill="x", pady=(0, 18))
        rows = self.storage.recent_history(100) if is_history else self.storage.common_phrases(100)
        box = tk.Listbox(self.content, bg=self.card, fg=self.fg, relief="flat",
                         font=("Microsoft JhengHei UI", 12), selectbackground=self.accent)
        box.pack(fill="both", expand=True)
        for row in rows:
            box.insert("end", row["text"])
        def use_selected() -> None:
            selection = box.curselection()
            if selection:
                self.root.clipboard_clear()
                self.root.clipboard_append(rows[selection[0]]["text"])
                self.status.set(self._t("已複製所選文字", "Selected text copied"))
        tk.Button(self.content, text=self._t("複製選取內容", "Copy selection"), command=use_selected,
                  bg=self.accent, fg="white", relief="flat", padx=14, pady=8).pack(anchor="e", pady=12)

    def show_settings(self) -> None:
        self._show_page("settings")

    def _render_settings(self) -> None:
        window = self.content
        style = ttk.Style()
        style.theme_use("clam")
        field = "#303A40" if self.dark_theme else "#E9ECEA"
        style.configure("Yulow.TCombobox", fieldbackground=field, background=field,
                        foreground=self.fg, bordercolor=self.border, arrowcolor=self.fg,
                        padding=5)
        style.map("Yulow.TCombobox", fieldbackground=[("readonly", field)],
                  background=[("readonly", field)], foreground=[("readonly", self.fg)])
        tk.Label(window, text=self._t("設定", "Settings"), bg=self.bg, fg=self.fg,
                 font=("Microsoft JhengHei UI", 23, "bold")).pack(anchor="w", pady=(0, 18))
        auto = tk.BooleanVar(value=self.settings.auto_paste)
        traditional = tk.BooleanVar(value=self.settings.traditional_chinese)
        sounds = tk.BooleanVar(value=self.settings.sound_cues)
        for label, variable in [
            (self._t("辨識後自動貼上", "Paste after transcription"), auto),
            (self._t("中文轉換為臺灣繁體", "Convert Chinese to Traditional"), traditional),
            (self._t("播放提示音", "Play sound cues"), sounds),
        ]:
            tk.Checkbutton(window, text=label, variable=variable, bg=self.bg,
                           fg=self.fg, activebackground=self.bg, selectcolor=self.card,
                           font=("Microsoft JhengHei UI", 11)).pack(anchor="w", padx=4, pady=6)

        def chooser(label: str, value: tk.StringVar, choices: list[str]) -> None:
            row = tk.Frame(window, bg=self.bg)
            row.pack(fill="x", padx=4, pady=7)
            tk.Label(row, text=label, bg=self.bg, fg=self.fg, width=13,
                     anchor="w").pack(side="left")
            ttk.Combobox(row, textvariable=value, values=choices, state="readonly",
                         style="Yulow.TCombobox", width=26).pack(side="left", fill="x", expand=True)

        hotkey = tk.StringVar(value=self.settings.hotkey)
        chooser(self._t("快捷鍵", "Hotkey"), hotkey, ["Right Alt", "Right Ctrl", "F8"])
        language = tk.StringVar(value=self.settings.interface_language)
        chooser(self._t("介面語言", "Language"), language, ["繁體中文", "English"])
        theme = tk.StringVar(value=self.settings.theme)
        chooser(self._t("外觀", "Appearance"), theme, ["跟隨 Windows", "淺色", "深色"])

        import sounddevice as sd
        devices = [(None, self._t("系統預設麥克風", "System default microphone"))]
        try:
            devices.extend((index, str(device["name"])) for index, device in enumerate(sd.query_devices())
                           if device["max_input_channels"] > 0)
        except Exception:
            pass
        selected_mic = tk.StringVar(value=next((name if index is None else f"{index}: {name}"
                                                for index, name in devices
                                                if index == self.settings.microphone), devices[0][1]))
        microphone_labels = [name if index is None else f"{index}: {name}" for index, name in devices]
        chooser(self._t("麥克風", "Microphone"), selected_mic, microphone_labels)
        days = tk.StringVar(value=str(self.settings.keep_history_days))
        chooser(self._t("記錄保留天數", "History days"), days, ["7", "30", "90", "365"])
        grammar_labels = {
            "off": self._t("關閉", "Off"),
            "preview": self._t("僅整理標點", "Punctuation only"),
            "local_ai": self._t("本機 AI 校正（推薦）", "Local AI correction (recommended)"),
        }
        selected_grammar = tk.StringVar(value=grammar_labels.get(self.settings.grammar_mode, grammar_labels["local_ai"]))
        chooser(self._t("文法校正", "Grammar correction"), selected_grammar, list(grammar_labels.values()))
        model_row = tk.Frame(window, bg=self.bg)
        model_row.pack(fill="x", padx=4, pady=7)
        tk.Label(model_row, text=self._t("AI 模型", "AI model"), bg=self.bg, fg=self.fg, width=13,
                 anchor="w").pack(side="left")
        grammar_model = tk.StringVar(value=self.settings.grammar_model)
        tk.Entry(model_row, textvariable=grammar_model, bg=field, fg=self.fg, insertbackground=self.fg,
                 relief="flat", font=("Segoe UI", 10)).pack(side="left", fill="x", expand=True, ipady=6)
        tk.Label(window,
                 text=self._t("本機 AI 可校正中文、英文與日文，不設每日額度。請先安裝 Ollama，並下載 qwen3:4b 模型。",
                              "Local AI corrects Chinese, English, and Japanese with no daily quota. Install Ollama, then download qwen3:4b."),
                 bg=self.bg, fg=self.muted, justify="left", wraplength=620,
                 font=("Microsoft JhengHei UI", 9)).pack(anchor="w", padx=4, pady=(2, 0))
        RoundedButton(window, text=self._t("本機 AI 安裝指南", "Local AI setup guide"),
                      command=self._show_grammar_setup, bg=self.border, fg=self.fg,
                      width=172, height=38, radius=11).pack(anchor="w", padx=4, pady=(10, 0))

        def save() -> None:
            self.settings.auto_paste = auto.get()
            self.settings.traditional_chinese = traditional.get()
            self.settings.sound_cues = sounds.get()
            self.settings.keep_history_days = int(days.get())
            self.settings.microphone = next((index for (index, _), label in zip(devices, microphone_labels)
                                             if label == selected_mic.get()), None)
            self.settings.interface_language = language.get()
            self.settings.theme = theme.get()
            self.settings.grammar_mode = next(
                (key for key, label in grammar_labels.items() if label == selected_grammar.get()), "local_ai"
            )
            self.settings.grammar_model = grammar_model.get().strip() or "qwen3:4b"
            if self.settings.hotkey != hotkey.get():
                self.hook.stop()
                self.settings.hotkey = hotkey.get()
                self.hook = RightAltHook(lambda: self.events.put(("toggle", None)),
                                        lambda error: self.events.put(("status", error)),
                                        self.settings.hotkey)
                self.hook.start()
            self.settings.save()
            self.storage.purge_old(self.settings.keep_history_days)
            self._set_palette()
            for widget in self.root.winfo_children():
                widget.destroy()
            self.root.configure(bg=self.bg)
            self.root.after(0, self._style_title_bar)
            self._build_ui()
            self.status.set(self._t("設定已儲存", "Settings saved"))

        self.settings_save_button = RoundedButton(self.footer, text=self._t("儲存設定", "Save settings"),
                                                   command=save, bg=self.accent,
                                                   width=120, height=44, radius=12)
        self.settings_save_button.pack(side="right")

    def toggle(self) -> None:
        if self.processing:
            self._sound_error()
            return
        if self.recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self) -> None:
        try:
            import sounddevice as sd
            self.target_hwnd = foreground_window()
            self.frames.clear()

            def callback(indata, frame_count, timing, status) -> None:
                self.frames.append(indata.copy())

            self.stream = sd.InputStream(
                device=self.settings.microphone,
                samplerate=SAMPLE_RATE, channels=1, dtype="int16", callback=callback
            )
            self.stream.start()
        except Exception as exc:
            self._sound_error()
            messagebox.showerror(APP_NAME, f"無法開啟麥克風：\n{exc}")
            return

        self.recording = True
        self._sound_start()
        self._show_overlay(self._t("● 正在聆聽 · 再按一次停止", "● Listening · Press again to stop"), "#8DDFC1")
        self.mic_button.set_style(self._t("■  停止", "■  Stop"), "#C96859")
        self.status.set("正在聆聽… 再按一下右 Alt 停止")
        self.preview.set("請開始說話")
        if hasattr(self, "recording_indicator"):
            self.recording_indicator.configure(text=self._t("●  錄音中", "●  Recording"), fg="#F18C84")
        if hasattr(self, "transcript_state"):
            self.transcript_state.configure(text=self._t("正在聆聽", "Listening"), fg=self.accent)
        self._set_grammar_card("—", "—", self._t("等待語音完成", "Waiting for dictation"), False)

    def stop_recording(self) -> None:
        self.recording = False
        self._sound_stop()
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        if not self.frames:
            self._reset("沒有收到聲音，請再試一次")
            return
        self.processing = True
        self._show_overlay(self._t("正在辨識語音…", "Transcribing…"), "#F2D997", loading=True)
        self.mic_button.set_style(self._t("辨識中", "Working"), "#9AA9A3", disabled=True)
        self.status.set("正在辨識中英日語音")
        if hasattr(self, "recording_indicator"):
            self.recording_indicator.configure(text=self._t("●  辨識中", "●  Working"), fg="#F2D997")
        if hasattr(self, "transcript_state"):
            self.transcript_state.configure(text=self._t("正在辨識", "Transcribing"), fg="#F2D997")
        threading.Thread(target=self._recognize, daemon=True).start()

    def _recognize(self) -> None:
        path: Path | None = None
        try:
            audio = np.concatenate(self.frames, axis=0)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as file:
                path = Path(file.name)
            save_wav(path, audio, SAMPLE_RATE)
            text, language = self.transcriber.transcribe(
                path, lambda value: self.events.put(("status", value))
            )
            text = polish_punctuation(text, language)
            if self.settings.traditional_chinese and language == "zh":
                try:
                    from opencc import OpenCC
                    text = OpenCC("s2twp").convert(text)
                except ImportError:
                    pass
            source_text = text
            grammar_applied = False
            grammar_message = ""
            if self.settings.grammar_mode == "local_ai":
                self.events.put(("status", self._t("正在用本機 AI 校正文法…", "Correcting grammar locally…")))
                try:
                    text = correct_with_ollama(
                        text, language, self.settings.grammar_model, self.settings.grammar_endpoint
                    )
                    grammar_applied = True
                except GrammarServiceUnavailable:
                    grammar_message = self._t(
                        "本機 AI 尚未啟用，已保留標點整理", "Local AI is not ready; punctuation cleanup was kept"
                    )
            self.events.put(("recognized", (text, language, source_text, grammar_applied, grammar_message)))
        except Exception as exc:
            self.events.put(("error", str(exc)))
        finally:
            if path:
                path.unlink(missing_ok=True)

    def _poll_events(self) -> None:
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == "toggle":
                    self.toggle()
                elif kind == "status":
                    self.status.set(str(data))
                elif kind == "recognized":
                    text, language, source_text, grammar_applied, grammar_message = data
                    self._deliver(text, language, source_text, grammar_applied, grammar_message)
                elif kind == "error":
                    self._sound_error()
                    self.preview.set("辨識失敗")
                    self._reset(str(data))
                    self._show_overlay(self._t("辨識失敗", "Transcription failed"), "#F2A99E")
                    self._hide_overlay_later(2500)
                elif kind == "show_main":
                    self._show_main()
                elif kind == "grammar_setup_check":
                    if not bool(data):
                        self._show_grammar_setup(first_run=True)
                elif kind == "quit":
                    self.close()
        except queue.Empty:
            pass
        self.root.after(50, self._poll_events)

    def _deliver(self, text: str, language: str | None, source_text: str = "", grammar_applied: bool = False,
                 grammar_message: str = "") -> None:
        self.last_text = text
        self.last_language = language
        self.storage.add_history(text, language)
        self.preview.set(text)
        if hasattr(self, "recording_indicator"):
            self.recording_indicator.configure(text=self._t("●  已完成", "●  Complete"), fg=self.accent)
        if hasattr(self, "transcript_state"):
            self.transcript_state.configure(text=self._t("辨識完成", "Complete"), fg=self.accent)
        if grammar_applied:
            self._set_grammar_card(source_text, text, self._t("✓ AI 文法校正完成", "✓ AI correction complete"), True)
        elif self.settings.grammar_mode == "local_ai":
            self._set_grammar_card(source_text, text,
                                   grammar_message or self._t("本機 AI 無法完成校正", "Local AI could not correct"),
                                   False)
        elif self.settings.grammar_mode == "preview":
            self._set_grammar_card(source_text, text, self._t("已整理標點", "Punctuation cleaned"), False)
        else:
            self._set_grammar_card(source_text, text, self._t("文法校正未啟用", "Grammar correction is off"), False)
        self._show_overlay(text, "#8DDFC1")
        self._hide_overlay_later(3000)
        if self.settings.auto_paste:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update()
            focus_window(self.target_hwnd)
            paste()
            self._reset(grammar_message or (
                self._t("已校正文法並輸入到原本的游標位置", "Grammar corrected and inserted")
                if grammar_applied else self._t("已輸入到原本的游標位置", "Inserted at the original cursor")
            ))
        else:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self._reset(grammar_message or (
                self._t("已校正文法，內容已複製", "Grammar corrected and copied")
                if grammar_applied else self._t("辨識完成，內容已複製", "Transcription copied")
            ))

    def undo_last(self) -> None:
        if not self.last_text:
            self.status.set("目前沒有可復原的輸入")
            return
        focus_window(self.target_hwnd)
        undo()
        self.status.set("已送出復原指令")

    def favorite_last(self) -> None:
        if not self.last_text:
            self.status.set("請先完成一次語音輸入")
            return
        self.storage.favorite(self.last_text)
        self.status.set("已收藏為常用句")

    def show_library(self) -> None:
        window = tk.Toplevel(self.root)
        window.title(" ")
        window.geometry("650x420")
        window.attributes("-topmost", True)
        window.after(0, lambda: style_title_bar(window, self.dark_theme, self.bg))
        notebook = ttk.Notebook(window)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)
        self._build_list_tab(notebook, "最近記錄", self.storage.recent_history())
        self._build_list_tab(notebook, "常用句", self.storage.common_phrases())

    def _build_list_tab(self, notebook: ttk.Notebook, title: str, rows: list[dict]) -> None:
        frame = ttk.Frame(notebook)
        notebook.add(frame, text=title)
        listbox = tk.Listbox(frame, font=("Microsoft JhengHei UI", 10))
        listbox.pack(fill="both", expand=True, padx=8, pady=8)
        for row in rows:
            suffix = f"  ×{row['uses']}" if "uses" in row else ""
            listbox.insert("end", row["text"] + suffix)

        def use_selected() -> None:
            selected = listbox.curselection()
            if not selected:
                return
            text = rows[selected[0]]["text"]
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            focus_window(self.target_hwnd)
            paste()

        ttk.Button(frame, text="輸入選中的句子", command=use_selected).pack(pady=(0, 8))

    def _reset(self, status: str) -> None:
        self.processing = False
        self.mic_button.set_style(self._t("●  錄音", "●  Record"), self.accent)
        self.status.set(status)

    def _sound_start(self) -> None:
        if self.settings.sound_cues:
            play("start")

    def _sound_stop(self) -> None:
        if self.settings.sound_cues:
            play("stop")

    def _sound_error(self) -> None:
        if self.settings.sound_cues:
            play("error")

    def close(self) -> None:
        if self.stream:
            self.stream.stop()
            self.stream.close()
        self.hook.stop()
        self._hide_overlay()
        self.tray.stop()
        self.settings.save()
        self.root.destroy()


def main() -> None:
    if sys.platform != "win32":
        raise SystemExit("Yulow｜語落目前僅支援 Windows。")
    root = tk.Tk()
    App(root)
    root.mainloop()
