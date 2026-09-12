# src/makeup/cmd/commands.py
""" a module for direct execution of /usr/bin/ programs (and as named /+ aliased)
	by the system (e.g. rather than os.listdir, cmd.ll) in Python.
""" 
from __future__ import annotations

from collections import namedtuple
from pathlib import Path
import subprocess

import click

from makeup.command_set import CommandSet, command

# import re
# ps = Path('usr/bin/').iterdir()
# >>> 
# {'-', '.', '+'}


class CmdCommandss(CommandSet):
	name = "cmd"

	@command(
		context_settings={
			"ignore_unknown_options": True,
			"allow_extra_args": True,
		}
	)
	@click.argument("arguments", nargs=-1, type=click.UNPROCESSED)
	def ls(self, arguments: tuple[str, ...]) -> None:
		subprocess.run(["ls", *arguments], check=True)




def _build_class_dot_access(dirs: list):
	""" e.g. 

		class bin:
			pass

		class usr:
			bin = bin

		-> usr.bin.ls()
	"""
	for i, d in enumerate(dirs).reverse():

		if not d in globals():
			if i+1 < len(dirs):
				encap = f'{dirs[i+1]} = {dirs[i+1]}'
			else:
				encap = 'pass'

			c = f"""class {d}:\n\t{encap}"""

		exec(c, globals(), locals())


def _build_cmd_mtd():
	# .run('{cmd}', *args, **kwargs) -> 
	# todo : kwarg-> 
	# arg -> 
	# todo : deal with flags --global etc. 
	for cmd in Path('/usr/bin').iterdir():
		notallowed = set([f.group(0) for f in [re.search(r'[^\w \d]', str(e).split('/')[-1]) for e in ps] if f])
		for i in notallowed: 
			# replace e.g. {'.', '-', '+'}, which are not allowed in Python function names
			cmd = str(cmd).split('/')[-1].replace(i, '_')

		mtd = f"""def {cmd}(self, *args, **kwargs):
		\t'''a python wrapper for /usr/bin/{cmd}'''
		\treturn subprocess.run('{cmd}', *args, **kwargs)"""

		exec(mtd, globals(), locals())
		setattr(bin, cmd, eval(f'{cmd}'))

	usr = usr()

_build_obj_bin()

print(usr.bin.ll())




class CmdCommands(CommandSet):
	"""Run selected system commands."""

	name = "cmd"

	@command(
		context_settings={
			"ignore_unknown_options": True,
			"allow_extra_args": True,
		}
	)
	@click.argument("program")
	@click.argument(
		"arguments",
		nargs=-1,
		type=click.UNPROCESSED,
	)
	def run(
		self,
		program: str,
		arguments: tuple[str, ...],
	) -> None:
		"""Run a program with its remaining arguments."""

		result = subprocess.run(
			[program, *arguments],
			check=False,
		)

		if result.returncode:
			raise click.exceptions.Exit(result.returncode)

	def resolve_program(self, name: str) -> str:
		"""An internal helper; this is not a command."""

		return name
