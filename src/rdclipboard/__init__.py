"""Synchronize the system clipboard with a text file."""

from __future__ import annotations

import argparse
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Protocol

import pyperclip

logger = logging.getLogger(__name__)


class Clipboard(Protocol):
    """Interface used by the synchronizer to access a clipboard."""

    def copy(self, text: str) -> None:
        """Set the clipboard text."""

    def paste(self) -> str:
        """Return the clipboard text."""


class ClipboardSync:
    """Keep a UTF-8 text file and a clipboard synchronized."""

    def __init__(self, path: Path, clipboard: Clipboard | None = None) -> None:
        self.path = path.expanduser()
        self.clipboard = pyperclip if clipboard is None else clipboard
        self._last_file_content: str | None = None
        self._last_clipboard_content: str | None = None

    def initialize(self) -> None:
        """Initialize the file and clipboard according to the startup policy."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            content = self._read_file()
            self.clipboard.copy(content)
        else:
            content = self.clipboard.paste()
            self._write_file(content)

        self._last_file_content = content
        self._last_clipboard_content = content

    def sync_once(self) -> None:
        """Propagate one detected change in either direction."""
        file_content = self._read_file()
        clipboard_content = self.clipboard.paste()

        if file_content != self._last_file_content:
            self.clipboard.copy(file_content)
            clipboard_content = file_content
            logger.info("Loaded changed file contents into the clipboard")
        elif clipboard_content != self._last_clipboard_content:
            self._write_file(clipboard_content)
            file_content = clipboard_content
            logger.info("Saved changed clipboard contents to %s", self.path)

        self._last_file_content = file_content
        self._last_clipboard_content = clipboard_content

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
        "--verbose",
        action="store_true",
        help="enable informational logging",
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
