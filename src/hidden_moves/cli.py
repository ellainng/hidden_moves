"""The CLI is an adapter around explicitly assembled Python capabilities."""

import click

from hidden_moves import MoveError, Moves, discover_providers, load_provider
from hidden_moves.builtins import builtin_registry
from hidden_moves.commands.capabilities import (
	json_commands,
	move_commands,
	plugin_commands,
	text_commands,
)
from hidden_moves.commands.system import CmdCommands


@click.group()
@click.option("--plugin", "plugins", multiple=True, help="Explicitly load an installed provider.")
@click.pass_context
def main(context: click.Context, plugins: tuple[str, ...]) -> None:
	"""Discover and use reusable Python capabilities."""
	registry = builtin_registry()
	if plugins:
		entries = discover_providers()
		for name in plugins:
			matches = [entry for entry in entries if entry.name == name]
			if len(matches) != 1:
				reason = "not installed" if not matches else "advertised by multiple packages"
				raise click.ClickException(f"Provider {name!r} is {reason}.")
			try:
				load_provider(matches[0], registry)
			except MoveError as error:
				raise click.ClickException(str(error)) from error
	context.obj = Moves(registry=registry)


main.add_command(CmdCommands().as_group())
main.add_command(move_commands)
main.add_command(plugin_commands)
main.add_command(text_commands)
main.add_command(json_commands)
