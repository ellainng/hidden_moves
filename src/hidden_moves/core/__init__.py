"""Generic capability machinery with no CLI or domain dependencies."""

from .discovery import ENTRY_POINT_GROUP, discover_providers, load_provider
from .definition import MoveAnnotations, MoveDefinition
from .errors import (
	MoveBindingError,
	MoveCollisionError,
	MoveError,
	MoveSchemaError,
	ProviderLoadError,
	UnknownMoveError,
)
from .moves import Moves
from .registry import Registry
from .spec import MoveSpec

__all__ = [
	"ENTRY_POINT_GROUP",
	"MoveAnnotations",
	"MoveBindingError",
	"MoveCollisionError",
	"MoveError",
	"MoveSchemaError",
	"MoveDefinition",
	"MoveSpec",
	"Moves",
	"ProviderLoadError",
	"Registry",
	"UnknownMoveError",
	"discover_providers",
	"load_provider",
]
