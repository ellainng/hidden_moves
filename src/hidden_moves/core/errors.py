"""Errors at capability registration, binding, and provider boundaries."""


class MoveError(Exception):
	"""Base class for errors reported by Hidden Moves."""


class MoveCollisionError(MoveError, ValueError):
	"""A move would replace a name or namespace without permission."""


class UnknownMoveError(MoveError, LookupError):
	"""No move is registered under the requested name."""


class MoveBindingError(MoveError, TypeError):
	"""The current target cannot be bound to a move."""


class ProviderLoadError(MoveError):
	"""An explicitly selected provider could not be loaded."""
