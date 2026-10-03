"""Errors before invocation and at structured-result boundaries."""

from hidden_moves.core.errors import MoveError


class CapabilityExposureError(MoveError, ValueError):
	"""A selected capability cannot be exposed through the supported contract."""


class CapabilityArgumentError(MoveError, ValueError):
	"""Structured arguments failed validation before capability execution."""


class CapabilityResultError(MoveError, ValueError):
	"""A result cannot be represented by its structured output contract."""
