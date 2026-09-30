import click

from hidden_moves.cmd.commands import CmdCommands



@click.group()
def main() -> None:
	"""hidden_moves command-line tools."""


main.add_command(CmdCommands().as_group())