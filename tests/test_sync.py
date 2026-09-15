from pathlib import Path

from rdclipboard import ClipboardSync


class FakeClipboard:
    def __init__(self, content: str = "") -> None:
        self.content = content

    def copy(self, text: str) -> None:
        self.content = text

    def paste(self) -> str:
        return self.content


def test_new_file_is_initialized_from_clipboard(tmp_path: Path) -> None:
    clipboard = FakeClipboard("from clipboard")
    path = tmp_path / "clipboard.txt"

    sync = ClipboardSync(path, clipboard)
    sync.initialize()

    assert path.read_text(encoding="utf-8") == "from clipboard"


def test_existing_file_is_initialized_into_clipboard(tmp_path: Path) -> None:
    path = tmp_path / "clipboard.txt"
    path.write_text("from file", encoding="utf-8")
    clipboard = FakeClipboard("old clipboard")

    ClipboardSync(path, clipboard).initialize()

    assert clipboard.content == "from file"


def test_clipboard_change_is_saved(tmp_path: Path) -> None:
    path = tmp_path / "clipboard.txt"
    path.write_text("initial", encoding="utf-8")
    clipboard = FakeClipboard()
    sync = ClipboardSync(path, clipboard)
    sync.initialize()
    clipboard.copy("updated")

    sync.sync_once()

    assert path.read_text(encoding="utf-8") == "updated"


def test_file_change_is_loaded(tmp_path: Path) -> None:
    path = tmp_path / "clipboard.txt"
    path.write_text("initial", encoding="utf-8")
    clipboard = FakeClipboard()
    sync = ClipboardSync(path, clipboard)
    sync.initialize()
    path.write_text("updated", encoding="utf-8")

    sync.sync_once()

    assert clipboard.content == "updated"
