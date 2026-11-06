from __future__ import annotations

import json
import re
from urllib.error import URLError
from urllib.request import Request, urlopen


class GrammarServiceUnavailable(RuntimeError):
    """Raised when the user's local grammar model is not ready."""


def _language_name(language: str | None) -> str:
    return {"zh": "Traditional Chinese", "en": "English", "ja": "Japanese"}.get(
        language or "", "the original language"
    )


def _grammar_prompt(text: str, language: str | None) -> str:
    return f"""You are a careful multilingual proofreader. Correct grammar, punctuation,
spelling, and natural phrasing in the following { _language_name(language) } dictation.

Keep the speaker's intended meaning, level of formality, names, numbers, URLs, and code.
For Chinese, write Traditional Chinese used in Taiwan. For mixed-language text, preserve each
language and correct only what needs correction. Do not translate. Do not add information.
Return only the corrected text with no explanation, heading, quotation marks, or markdown.

Text:
{ text }"""


def correct_with_ollama(
    text: str,
    language: str | None,
    model: str,
    endpoint: str = "http://127.0.0.1:11434/api/chat",
    timeout: int = 120,
) -> str:
    """Correct dictation with a locally running Ollama model.

    Ollama runs on the user's own computer, so this needs no API key or daily quota.
    """
    if not text.strip():
        return text
    payload = json.dumps(
        {
            "model": model,
            "stream": False,
            "messages": [{"role": "user", "content": _grammar_prompt(text, language)}],
            "options": {"temperature": 0.1},
        }
    ).encode("utf-8")
    request = Request(endpoint, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError, OSError) as exc:
        raise GrammarServiceUnavailable("找不到本機 AI 服務") from exc
    except (ValueError, KeyError, TypeError) as exc:
        raise GrammarServiceUnavailable("本機 AI 回傳的資料無法使用") from exc

    corrected = str(data.get("message", {}).get("content", "")).strip()
    if not corrected:
        raise GrammarServiceUnavailable("本機 AI 沒有回傳校正結果")
    return corrected


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
