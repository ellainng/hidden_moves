"""Metadata discovery and explicit activation of experimental providers."""

from __future__ import annotations

from dataclasses import replace
from importlib.metadata import EntryPoint, entry_points

from .errors import ProviderLoadError
from .registry import Registry
from .spec import MoveSpec

ENTRY_POINT_GROUP = "hidden_moves.moves"


def discover_providers() -> tuple[EntryPoint, ...]:
	"""Find installed integrations without importing their modules."""
	return tuple(sorted(
		entry_points(group=ENTRY_POINT_GROUP),
		key=lambda entry: (entry.name, entry.value),
	))


def load_provider(entry: EntryPoint, registry: Registry) -> tuple[MoveSpec, ...]:
	"""Load a zero-argument provider returning MoveSpecs, then register atomically."""
	try:
		provider = entry.load()
		if not callable(provider):
			raise TypeError("The entry point must reference a callable provider.")
		specs = []
		for spec in provider():
			if not isinstance(spec, MoveSpec):
				raise TypeError("Providers must return an iterable of MoveSpec objects.")
			specs.append(replace(spec, provider=entry.value))
		return registry.register_many(specs)
	except Exception as error:
		# Imports can fail for optional dependencies; leave other providers usable.
		raise ProviderLoadError(
			f"Could not load provider {entry.name!r} ({entry.value}): {error}"
		) from error
