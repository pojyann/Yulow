import json

import typelist_voice.grammar as grammar
from typelist_voice.grammar import correct_with_ollama, ollama_is_ready, polish_punctuation


def test_english_punctuation() -> None:
    assert polish_punctuation("hello world", "en") == "Hello world."


def test_japanese_punctuation() -> None:
    assert polish_punctuation("よろしくお願いします", "ja") == "よろしくお願いします。"


def test_mixed_content_is_not_rewritten() -> None:
    value = "明日の marketing meeting は 3時"
    assert polish_punctuation(value, "zh") == value + "。"


def test_local_ai_correction_uses_language_safe_prompt(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def read(self) -> bytes:
            return json.dumps({"message": {"content": "She goes to school every day."}}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

    def fake_open(request, timeout):
        captured["body"] = json.loads(request.data.decode())
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(grammar, "urlopen", fake_open)
    result = correct_with_ollama("she go school everyday", "en", "qwen3:4b")
    assert result == "She goes to school every day."
    assert captured["body"]["model"] == "qwen3:4b"
    assert "Return only the corrected text" in captured["body"]["messages"][0]["content"]


def test_ollama_check_requires_the_selected_model(monkeypatch) -> None:
    class FakeResponse:
        def read(self) -> bytes:
            return b'{"models":[{"name":"qwen3:4b"}]}'

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

    monkeypatch.setattr(grammar, "urlopen", lambda *args, **kwargs: FakeResponse())
    assert ollama_is_ready("qwen3:4b")
    assert not ollama_is_ready("another-model")
