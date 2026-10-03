"""Click adapts system-command results to terminal exit codes."""

import click

from hidden_moves import Moves
from hidden_moves.command_set import CommandSet, command


class CmdCommands(CommandSet):
	"""Run system programs with their original arguments."""

	name = "cmd"

	@command(
		context_settings={
			"ignore_unknown_options": True,
			"allow_extra_args": True,
		},
	)
	@click.argument("program")
	@click.argument("arguments", nargs=-1, type=click.UNPROCESSED)
	def run(self, program: str, arguments: tuple[str, ...]) -> None:
		moves = click.get_current_context().find_object(Moves)
		if moves is None:
			raise click.ClickException("The command requires a Hidden Moves context.")
		try:
			result = moves.cmd.run(program, arguments)
		except OSError as error:
			raise click.ClickException(str(error)) from error
		if result.returncode:
			raise click.exceptions.Exit(result.returncode)
