"""Synchronize the system clipboard with a text file."""

from __future__ import annotations

import argparse
import base64
import importlib
import io
import logging
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import pyperclip
from PIL import Image, ImageGrab

logger = logging.getLogger(__name__)

IMAGE_PREFIX = "data:image/png;base64,"


@dataclass(frozen=True)
class ClipboardItem:
    """A text or PNG image currently held by the clipboard."""

    kind: str
    data: str | bytes


class Clipboard(Protocol):
    """Interface used by the synchronizer to access a clipboard."""

    def get(self) -> ClipboardItem:
        """Return the current clipboard item."""

    def set(self, item: ClipboardItem) -> None:
        """Set the clipboard item."""


class SystemClipboard:
    """Read and write text and images through the native system clipboard."""

    def get(self) -> ClipboardItem:
        image = ImageGrab.grabclipboard()
        if isinstance(image, Image.Image):
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            return ClipboardItem("image", buffer.getvalue())
        return ClipboardItem("text", pyperclip.paste())

    def set(self, item: ClipboardItem) -> None:
        if item.kind == "text":
            pyperclip.copy(str(item.data))
            return
        if item.kind != "image" or not isinstance(item.data, bytes):
            raise ValueError(f"Unsupported clipboard item: {item.kind}")
        self._set_image(item.data)

    @staticmethod
    def _set_image(png_data: bytes) -> None:
        win32clipboard = importlib.import_module("win32clipboard")
        win32con = importlib.import_module("win32con")

        with Image.open(io.BytesIO(png_data)) as image:
            bitmap = io.BytesIO()
            image.convert("RGB").save(bitmap, format="BMP")
        dib_data = bitmap.getvalue()[14:]
        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32con.CF_DIB, dib_data)
        finally:
            win32clipboard.CloseClipboard()


class ClipboardSync:
    """Keep a UTF-8 text file and a system clipboard synchronized."""

    def __init__(self, path: Path, clipboard: Clipboard | None = None) -> None:
        self.path = path.expanduser()
        self.clipboard = SystemClipboard() if clipboard is None else clipboard
        self._last_file_content: str | None = None
        self._last_clipboard_item: ClipboardItem | None = None

    def initialize(self) -> None:
        """Initialize the file and clipboard according to the startup policy."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            file_content = self._read_file()
            item = decode_item(file_content)
            self.clipboard.set(item)
        else:
            item = self.clipboard.get()
            file_content = encode_item(item)
            self._write_file(file_content)

        self._last_file_content = file_content
        self._last_clipboard_item = item

    def sync_once(self) -> None:
        """Propagate one detected change in either direction."""
        file_content = self._read_file()
        clipboard_item = self.clipboard.get()

        if file_content != self._last_file_content:
            clipboard_item = decode_item(file_content)
            self.clipboard.set(clipboard_item)
            logger.info("Loaded changed file contents into the clipboard")
        elif clipboard_item != self._last_clipboard_item:
            file_content = encode_item(clipboard_item)
            self._write_file(file_content)
            logger.info("Saved changed clipboard contents to %s", self.path)

        self._last_file_content = file_content
        self._last_clipboard_item = clipboard_item

    def run(self, interval: float = 0.5) -> None:
        """Run until interrupted, checking both sources at ``interval`` seconds."""
        if interval <= 0:
            raise ValueError("interval must be greater than zero")
        self.initialize()
        logger.info("Synchronizing clipboard with %s", self.path)
        try:
            while True:
                self.sync_once()
                time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("Clipboard synchronization stopped")

    def _read_file(self) -> str:
        try:
            return self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            self._write_file("")
            return ""

    def _write_file(self, content: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            dir=self.path.parent,
            text=True,
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, self.path)
        except BaseException:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise


def encode_item(item: ClipboardItem) -> str:
    """Encode a clipboard item as text suitable for the sync file."""
    if item.kind == "text" and isinstance(item.data, str):
        return item.data
    if item.kind == "image" and isinstance(item.data, bytes):
        return IMAGE_PREFIX + base64.b64encode(item.data).decode("ascii")
    raise ValueError(f"Unsupported clipboard item: {item.kind}")


def decode_item(content: str) -> ClipboardItem:
    """Decode a sync file value into a clipboard item."""
    if not content.startswith(IMAGE_PREFIX):
        return ClipboardItem("text", content)
    try:
        return ClipboardItem(
            "image", base64.b64decode(content[len(IMAGE_PREFIX) :], validate=True)
        )
    except ValueError as error:
        raise ValueError("The sync file contains invalid base64 image data") from error


def _parse_args() -> argparse.Namespace:
    desktop_file = Path.home() / "Desktop" / "clipboard.txt"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--file",
        type=Path,
        default=desktop_file,
        help=f"text file to synchronize (default: {desktop_file})",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.5,
        help="seconds between checks (default: 0.5)",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="enable informational logging"
    )
    return parser.parse_args()


def main() -> None:
    """Run the clipboard synchronization service."""
    args = _parse_args()
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    ClipboardSync(args.file).run(args.interval)
