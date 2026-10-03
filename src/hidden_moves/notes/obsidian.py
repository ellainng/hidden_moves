"""Export an Obsidian vault's top-level notes when explicitly requested."""

from __future__ import annotations

from html import escape
from pathlib import Path
from urllib.parse import urlencode


def export_index(
	vault: str | Path,
	destination: str | Path | None = None,
	*,
	vault_name: str | None = None,
) -> Path:
	"""Write a complete HTML index without changing the working directory."""
	root = Path(vault).expanduser()
	if not root.is_dir():
		raise NotADirectoryError(f"Not an Obsidian vault directory: {root}")
	output = Path(destination) if destination is not None else root / "obsidian_index.html"
	items = []
	for note in sorted(root.glob("*.md"), key=lambda path: path.name):
		if not note.is_file():
			continue
		query = urlencode({
			"vault": vault_name if vault_name is not None else root.name,
			"file": note.stem,
		})
		link = escape(f"obsidian://open?{query}", quote=True)
		items.append(f'<li><a href="{link}">{escape(note.stem)}</a></li>')
	output.write_text(
		"<!DOCTYPE html>\n<html>\n<head><meta charset=\"utf-8\">"
		"<title>Obsidian Index</title></head>\n<body>\n"
		"<h1>Obsidian Index</h1>\n<ul>\n"
		+ "\n".join(items)
		+ "\n</ul>\n</body>\n</html>\n",
		encoding="utf-8",
	)
	return output
