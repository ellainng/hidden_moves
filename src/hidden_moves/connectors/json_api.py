"""An explicitly configured JSON GET client using Python's standard library."""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from typing import Any
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen


class JsonApiClient:
	"""Own connection settings; network work begins only when get is called."""

	def __init__(
		self,
		base_url: str,
		*,
		headers: Mapping[str, str] | None = None,
		timeout: float = 10.0,
		opener: Callable[..., AbstractContextManager[Any]] | None = None,
	) -> None:
		parts = urlsplit(base_url)
		if parts.scheme not in {"http", "https"} or not parts.netloc:
			raise ValueError("base_url must be an absolute HTTP or HTTPS URL.")
		if parts.query or parts.fragment:
			raise ValueError("Put query parameters on get(), not base_url.")
		if not math.isfinite(timeout) or timeout <= 0:
			raise ValueError("timeout must be positive and finite.")
		self.base_url = base_url.rstrip("/") + "/"
		self.timeout = timeout
		self._headers = {"Accept": "application/json", **(headers or {})}
		self._opener = opener if opener is not None else urlopen

	def get(
		self,
		path: str = "",
		*,
		params: Mapping[str, str] | None = None,
	) -> Any:
		"""Decode a JSON response from a path relative to the configured base URL."""
		parts = urlsplit(path)
		if parts.scheme or parts.netloc or parts.fragment:
			raise ValueError("path must be relative and must not contain a URL fragment.")
		url = urljoin(self.base_url, path.lstrip("/"))
		if params:
			url += ("&" if "?" in url else "?") + urlencode(params)
		request = Request(url, headers=self._headers)
		with self._opener(request, timeout=self.timeout) as response:
			return json.load(response)
