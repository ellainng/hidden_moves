""" clone repositories for a user 
	note : requires pre-/authentication 
"""
import subprocess
from pathlib import Path

GH_CLONE_REPO_PATH = Path.home() / 'Documents' / 'Projects' / '_references' / '_gh'

repos = {
	'curt15': [
		'mobilenotes',
		'notes',
		'Apple-Notes',
		'training',
		'jamf',
		'machine_learning_andrew_ng',
		'modern-apis-with-fastapi-bk',
		'pytest-bk',
		'sqlconn',
		'pn_scrape',
		'scripts',
		'msbash',
		'ufc_scrape',
		'turnbased',
		'internet_radio_scrape',
		'bssites',
		'prettydev'
		]
	}


if __name__ == '__main__':

	for user, user_repos in repos.items():

		for repo in user_repos:
			loc_path = Path(GH_CLONE_REPO_PATH / user / repo)

			if (loc_path / '.git').is_dir():
				print(f"Skipping existing repository: \n\t{loc_path}\n...")
				print('consider git pull instead !\n')
				continue

			if loc_path.exists():
				print(f'Destination exists, but is not a repo: \n\t{loc_path}\n...')
				print('consider git init instead !\n')
				continue
			
			# os.makedirs(loc_path.parent, exist_ok=True) 
			loc_path.parent.mkdir(parents=True, exist_ok=True)

			# results = []

			try:
				result = subprocess.run(
					args=[
						'git', 
						'clone', 
						f'https://github.com/{user}/{repo}', 
						loc_path
						], 
					check=True,
					capture_output=True,
					text=True
					)
			except FileNotFoundError:
				print('Could not find the git executable.')
				print("consider installing git (e.g. 'brew install git')")
			except subprocess.CalledProcessError as e:
				print(f'{repo}: failed with exit code {e.returncode}')
				print(e.stderr or e.stdout or 'No Output.')
			else:
				for name in ('args', 'returncode', 'stdout', 'stderr'):
					print(f'{name}: {getattr(result, name)}', '\n')

				print(f"{repo}: cloned successfully")

			# if results:
			# 	with open('log_github.txt', '+a') as f:
			# 		results = "\n".join([r for r in results])
			# 		f.write()