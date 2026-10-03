"""System-command execution as an ordinary library capability."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence


def run(
	program: str,
	arguments: Sequence[str] = (),
	*,
	check: bool = False,
	capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
	"""Run an argument vector without shell expansion and return its result."""
	return subprocess.run(
		[program, *arguments],
		check=check,
		capture_output=capture_output,
		text=True,
	)
