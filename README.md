# rdclipboard

Keep your system clipboard synchronized with a text file on your desktop.

## Usage

Install the project with `uv sync`, then start the service:

```text
uv run rdclipboard
```

The default file is `~/Desktop/clipboard.txt`. An existing file is loaded into
the clipboard when the service starts. If the file does not exist, its initial
contents come from the current clipboard.

The service checks both the file and clipboard twice per second. Use `Ctrl+C`
to stop it. A different file or polling interval can be selected with:

```text
uv run rdclipboard --file C:\path\to\clipboard.txt --interval 1 --verbose
```
