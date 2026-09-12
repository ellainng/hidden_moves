import click

from makeup.cmd.commands import CmdCommands



@click.group()
def main() -> None:
	"""Makeup command-line tools."""


main.add_command(CmdCommands().as_group())