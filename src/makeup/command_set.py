# src/makeup/command_set.py
""" A safe base class for a related collection of click commands.

The important distinction is:
- Public methods can be ordinary helper methods.
- Only methods decorated with @command become CLI commands.
- Each class becomes a Click group.
- Decorators such as @click.argument and @click.option still work.
"""
from __future__ import annotations

import functools
import inspect
from collections.abc import Callable
from typing import Any

import click



def command(
	name: str | None = None,
	**command_options: Any,
):
	"""Mark a CommandSet method as a Click command."""

	def decorate(method: Callable[..., Any]) -> Callable[..., Any]:
		method.__makeup_command__ = {
			"name": name,
			"options": command_options,
		}
		return method

	return decorate



class CommandSet:
	"""Base class for a related collection of CLI commands."""

	name: str | None = None
	help: str | None = None

	def as_group(self, name: str | None = None) -> click.Group:
		group_name = name or self.name or type(self).__name__.lower()

		group = click.Group(
			name=group_name,
			help=self.help or inspect.getdoc(type(self)),
		)

		for method_name, method in inspect.getmembers(
			self,
			predicate=inspect.ismethod,
		):
			metadata = getattr(method, "__makeup_command__", None)

			if metadata is None:
				continue

			@functools.wraps(method)
			def callback(
				*args: Any,
				__method: Callable[..., Any] = method,
				**kwargs: Any,
			) -> Any:
				return __method(*args, **kwargs)

			command_name = (
				metadata["name"]
				or method_name.replace("_", "-")
			)

			click_command = click.command(
				name=command_name,
				**metadata["options"],
			)(callback)

			group.add_command(click_command)

		return group