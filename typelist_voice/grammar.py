from __future__ import annotations

import re


def polish_punctuation(text: str, language: str | None) -> str:
    """Safe local cleanup. It never rewrites meaning."""
    cleaned = re.sub(r"\s+([,.!?;:，。！？；：])", r"\1", text.strip())
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    if language == "en" and cleaned:
        cleaned = cleaned[0].upper() + cleaned[1:]
        if cleaned[-1] not in ".!?":
            cleaned += "."
    elif language in {"zh", "ja"} and cleaned and cleaned[-1] not in "。！？!?":
        cleaned += "。"
    return cleaned


def grammar_note(language: str | None) -> str:
    if language in {"en", "ja"}:
        return "已完成本機標點整理；完整文法改寫將在本機 AI 模組啟用後提供"
    return "已整理標點"
