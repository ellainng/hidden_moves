"""Application composition: ordinary library functions registered explicitly."""

import json

from .core import MoveSpec, Registry
from .kit.cmd import run
from .kit.text import slugify
from .notes.obsidian import export_index


def builtin_moves() -> tuple[MoveSpec, ...]:
	return (
		MoveSpec(name="slugify", namespace="text", func=slugify),
		MoveSpec(
			name="dumps",
			namespace="io.json",
			func=json.dumps,
			bind_target=True,
			description="Serialize the current target as JSON.",
		),
		MoveSpec(name="run", namespace="cmd", func=run),
		MoveSpec(name="export_index", namespace="notes.obsidian", func=export_index),
	)


def builtin_registry() -> Registry:
	registry = Registry()
	registry.register_many(builtin_moves())
	return registry
