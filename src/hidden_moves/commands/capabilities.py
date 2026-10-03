"""Thin Click adapters for capability inspection and example moves."""

import json

import click

from hidden_moves import MoveError, Moves, discover_providers


@click.group(name="moves")
def move_commands() -> None:
	"""Inspect registered capabilities."""


@move_commands.command(name="list")
@click.pass_obj
def list_moves(moves: Moves) -> None:
	for spec in moves.moves():
		click.echo(f"{spec.qualified_name}\t{spec.summary}")


@move_commands.command(name="show")
@click.argument("name")
@click.pass_obj
def show_move(moves: Moves, name: str) -> None:
	try:
		click.echo(json.dumps(moves.explain(name), indent=2))
	except MoveError as error:
		raise click.ClickException(str(error)) from error


@click.group(name="plugins")
def plugin_commands() -> None:
	"""Inspect installed provider metadata."""


@plugin_commands.command(name="list")
def list_plugins() -> None:
	for entry in discover_providers():
		click.echo(f"{entry.name}\t{entry.value}")


@click.group(name="text")
def text_commands() -> None:
	"""Reusable text operations."""


@text_commands.command(name="slugify")
@click.argument("value")
@click.pass_obj
def slugify(moves: Moves, value: str) -> None:
	click.echo(moves.text.slugify(value))


@click.group(name="json")
def json_commands() -> None:
	"""JSON serialization through a target-bound move."""


@json_commands.command(name="dumps")
@click.argument("value")
@click.option("--indent", type=click.IntRange(min=0), default=None)
@click.pass_obj
def dump_json(moves: Moves, value: str, indent: int | None) -> None:
	try:
		target = json.loads(value)
	except json.JSONDecodeError as error:
		raise click.BadParameter(str(error), param_hint="value") from error
	bound = Moves(target, registry=moves.registry, context=moves.context)
	click.echo(bound.io.json.dumps(indent=indent))
