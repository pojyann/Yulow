from pathlib import Path

from typelist_voice.storage import Storage


def test_history_and_common_phrases(tmp_path: Path) -> None:
    store = Storage(tmp_path / "test.db")
    store.add_history("Hello world", "en")
    store.add_history("Hello world", "en")
    assert store.recent_history()[0]["text"] == "Hello world"
    assert store.common_phrases()[0]["uses"] == 2


def test_favorite_phrase_appears(tmp_path: Path) -> None:
    store = Storage(tmp_path / "test.db")
    store.favorite("よろしくお願いします。")
    assert store.common_phrases()[0]["favorite"] == 1
