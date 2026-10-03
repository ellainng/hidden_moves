"""Small text helpers that work independently of the capability registry."""

import re
import unicodedata


def slugify(value: str) -> str:
	"""Convert text into a lowercase ASCII slug separated by hyphens."""
	ascii_text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
	return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
