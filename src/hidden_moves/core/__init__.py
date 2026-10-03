"""Generic capability machinery with no CLI or domain dependencies."""

from .discovery import ENTRY_POINT_GROUP, discover_providers, load_provider
from .errors import (
	MoveBindingError,
	MoveCollisionError,
	MoveError,
	ProviderLoadError,
	UnknownMoveError,
)
from .moves import Moves
from .registry import Registry
from .spec import MoveSpec

__all__ = [
	"ENTRY_POINT_GROUP",
	"MoveBindingError",
	"MoveCollisionError",
	"MoveError",
	"MoveSpec",
	"Moves",
	"ProviderLoadError",
	"Registry",
	"UnknownMoveError",
	"discover_providers",
	"load_provider",
]
