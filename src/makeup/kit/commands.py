""" a module for direct execution of /usr/bin/ programs (and as named /+ aliased)
	by the system (e.g. rather than os.listdir, cmd.ll) in Python.
""" 
import os
import subprocess
# import re

from collections import namedtuple

# import click 

# TODO: ...

class bin:
	pass



class usr:
	bin = bin



def build_obj_bin():
	# .run('{cmd}', *args, **kwargs) -> 
	# todo : kwarg-> 
	# arg -> 
	for cmd in os.listdir('/usr/bin'):
		if not '.' in str(cmd) or '-' in str(cmd):
			# x, y = cmd.split('.')
			# setattr(namedtuple(x, y)
			pass
		else:

			mtd = f"""def {cmd}(self, *args, **kwargs):
			\t'''a python wrapper for /usr/bin/{cmd}'''
			\treturn subprocess.run('{cmd}', *args, **kwargs)"""

			exec(mtd, globals(), locals())
			setattr(bin, cmd, eval(f'{cmd}'))

build_obj_bin()

print(usr.bin.ll())
