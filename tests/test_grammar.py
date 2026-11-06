from typelist_voice.grammar import polish_punctuation


def test_english_punctuation() -> None:
    assert polish_punctuation("hello world", "en") == "Hello world."


def test_japanese_punctuation() -> None:
    assert polish_punctuation("よろしくお願いします", "ja") == "よろしくお願いします。"


def test_mixed_content_is_not_rewritten() -> None:
    value = "明日の marketing meeting は 3時"
    assert polish_punctuation(value, "zh") == value + "。"
