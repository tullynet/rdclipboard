import base64
from pathlib import Path

from rdclipboard import ClipboardItem, ClipboardSync, decode_item, encode_item


class FakeClipboard:
    def __init__(self, item: ClipboardItem) -> None:
        self.item = item

    def get(self) -> ClipboardItem:
        return self.item

    def set(self, item: ClipboardItem) -> None:
        self.item = item


def test_new_file_is_initialized_from_clipboard(tmp_path: Path) -> None:
    clipboard = FakeClipboard(ClipboardItem("text", "from clipboard"))
    path = tmp_path / "clipboard.txt"

    ClipboardSync(path, clipboard).initialize()

    assert path.read_text(encoding="utf-8") == "from clipboard"


def test_existing_file_is_initialized_into_clipboard(tmp_path: Path) -> None:
    path = tmp_path / "clipboard.txt"
    path.write_text("from file", encoding="utf-8")
    clipboard = FakeClipboard(ClipboardItem("text", "old clipboard"))

    ClipboardSync(path, clipboard).initialize()

    assert clipboard.item == ClipboardItem("text", "from file")


def test_clipboard_change_is_saved(tmp_path: Path) -> None:
    path = tmp_path / "clipboard.txt"
    path.write_text("initial", encoding="utf-8")
    clipboard = FakeClipboard(ClipboardItem("text", "old"))
    sync = ClipboardSync(path, clipboard)
    sync.initialize()
    clipboard.item = ClipboardItem("text", "updated")

    sync.sync_once()

    assert path.read_text(encoding="utf-8") == "updated"


def test_file_change_is_loaded(tmp_path: Path) -> None:
    path = tmp_path / "clipboard.txt"
    path.write_text("initial", encoding="utf-8")
    clipboard = FakeClipboard(ClipboardItem("text", "old"))
    sync = ClipboardSync(path, clipboard)
    sync.initialize()
    path.write_text("updated", encoding="utf-8")

    sync.sync_once()

    assert clipboard.item == ClipboardItem("text", "updated")


def test_image_round_trips_as_base64() -> None:
    image_data = b"png bytes"
    encoded = encode_item(ClipboardItem("image", image_data))

    assert encoded.startswith("data:image/png;base64,")
    assert decode_item(encoded) == ClipboardItem("image", image_data)


def test_image_clipboard_change_is_saved(tmp_path: Path) -> None:
    path = tmp_path / "clipboard.txt"
    path.write_text("initial", encoding="utf-8")
    image_data = b"png bytes"
    clipboard = FakeClipboard(ClipboardItem("text", "old"))
    sync = ClipboardSync(path, clipboard)
    sync.initialize()
    clipboard.item = ClipboardItem("image", image_data)

    sync.sync_once()

    assert (
        base64.b64decode(path.read_text(encoding="utf-8").split(",", 1)[1])
        == image_data
    )
