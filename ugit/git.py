'''TODO: "import stgit"'''
import os
import re
import types
import utils
import defaults
from cStringIO import StringIO

# A regex for matching the output of git(log|rev-list) --pretty=oneline
REV_LIST_REGEX = re.compile('([0-9a-f]+)\W(.*)')

def quote(argv):
	return ' '.join([ utils.shell_quote(arg) for arg in argv ])

def git(*args,**kwargs):
	gitcmd = 'git %s' % args[0]
	return utils.run_cmd(gitcmd, *args[1:], **kwargs)

def add(to_add, verbose=True):
	'''Invokes 'git add' to index the filenames in to_add.'''
	if not to_add:
		return 'No files to add.'
	return git('add', verbose=verbose, *to_add)

def add_or_remove(to_process):
	'''Invokes 'git add' to index the filenames in to_process that exist
	and 'git rm' for those that do not exist.'''

	if not to_process:
		return 'No files to add or remove.'

	to_add = []
	to_remove = []

	for filename in to_process:
		if os.path.exists(filename):
			to_add.append(filename)

	output = add(to_add)

	if len(to_add) == len(to_process):
		# to_process only contained unremoved files --
		# short-circuit the removal checks
		return output

	# Process files to remote
	for filename in to_process:
		if not os.path.exists(filename):
			to_remove.append(filename)
	output + '\n\n' + git('rm',*to_remove)

def apply(filename, indexonly=True, reverse=False):
	kwargs = {}
	if reverse:
		kwargs['reverse'] = True
	if indexonly:
		kwargs['index'] = True
		kwargs['cached'] = True
	argv = ['apply', filename]
	return git(*argv, **kwargs)

def branch(name=None, remote=False, delete=False):
	if delete and name:
		return git('branch', name, D=True)
	else:
		branches = map(lambda x: x.lstrip('* '),
				git('branch', r=remote).splitlines())
		if remote:
			remotes = []
			for branch in branches:
				if branch.endswith('/HEAD'):
					continue
				remotes.append(branch)
			return remotes
		return branches

def cat_file(objtype, sha1):
	return git('cat-file', objtype, sha1, raw=True)

def cherry_pick(revs, commit=False):
	"""Cherry-picks each revision into the current branch.
	Returns a list of command output strings (1 per cherry pick)"""

	if not revs: return []

	argv = [ 'cherry-pick' ]
	kwargs = {}
	if not commit:
		kwargs['n'] = True

	cherries = []
	for rev in revs:
		new_argv = argv + [rev]
		cherries.append(git(*new_argv, **kwargs))

	return '\n'.join(cherries)

def checkout(*args):
	return git('checkout', *args)

def commit(msg, amend=False):
	'''Creates a git commit.'''

	if not msg.endswith('\n'):
		msg += '\n'

	# Sure, this is a potential "security risk," but if someone
	# is trying to intercept/re-write commit messages on your system,
	# then you probably have bigger problems to worry about.
	tmpfile = utils.get_tmp_filename()
	kwargs = {
		'F': tmpfile,
		'amend': amend,
	}

	# Create the commit message file
	file = open(tmpfile, 'w')
	file.write(msg)
	file.close()

	# Run 'git commit'
	output = git('commit', F=tmpfile, amend=amend)
	os.unlink(tmpfile)

	return ('git commit -F %s --amend %s\n\n%s'
		% ( tmpfile, amend, output ))

def create_branch(name, base, track=False):
	"""Creates a branch starting from base.  Pass track=True
	to create a remote tracking branch."""
	return git('branch', name, base, track=track)

def current_branch():
	'''Parses 'git branch' to find the current branch.'''
	branches = git('branch').splitlines()
	for branch in branches:
		if branch.startswith('* '):
			return branch.lstrip('* ')
	return 'Detached HEAD'

def diff(commit=None,filename=None, color=False,
		cached=True, with_diff_header=False,
		suppress_header=True, reverse=False):
	"Invokes git diff on a filepath."

	argv = []
	if commit:
		argv.append('%s^..%s' % (commit, commit))

	if filename:
		argv.append('--')
		if type(filename) is list:
			argv.extend(filename)
		else:
			argv.append(filename)

	kwargs = {
		'patch-with-raw': True,
		'unified': defaults.DIFF_CONTEXT,
	}

	diff = git('diff',
	           R=reverse,
	           color=color,
	           cached=cached,
	           *argv,
	           **kwargs)

	diff_lines = diff.splitlines()

	output = StringIO()
	start = False
	del_tag = 'deleted file mode '

	headers = []
	deleted = cached and not os.path.exists(filename)
	for line in diff_lines:
		if not start and '@@ ' in line and ' @@' in line:
			start = True
		if start or(deleted and del_tag in line):
			output.write(line + '\n')
		else:
			if with_diff_header:
				headers.append(line)
			elif not suppress_header:
				output.write(line + '\n')
	result = output.getvalue()
	output.close()
	if with_diff_header:
		return('\n'.join(headers), result)
	else:
		return result

def diffstat():
	return git('diff', 'HEAD^',
	           unified=defaults.DIFF_CONTEXT,
	           stat=True)

def diffindex():
	return git('diff',
	           unified=defaults.DIFF_CONTEXT,
	           stat=True,
	           cached=True)

def format_patch(revs):
	'''writes patches named by revs to the "patches" directory.'''
	num_patches = 1
	output = []
	kwargs = {
		'o': 'patches',
		'n': len(revs) > 1,
		'thread': True,
		'patch-with-stat': True,
	}
	for idx, rev in enumerate(revs):
		real_idx = idx + num_patches
		kwargs['start-number'] = real_idx
		revarg = '%s^..%s'%(rev,rev)
		output.append(git('format-patch', revarg, **kwargs))
		num_patches += output[-1].count('\n')
	return '\n'.join(output)

def config(key=None, value=None, local=False, asdict=False):
	if key:
		argv = ['config', key]
	else:
		argv = ['config']

	kwargs = {
		'global': local is False,
		'get': key and value is None,
		'list': asdict,
	}

	if asdict:
		return config_to_dict(git('config', **kwargs).splitlines())

	elif kwargs['get']:
		return git('config', key, **kwargs)

	elif key and value is not None:
		# git config category.key value
		strval = str(value)
		if type(value) is bool:
			# git uses "true" and "false"
			strval = strval.lower()
		return git('config', key, strval, **kwargs)
	else:
		msg = "oops in git.config(key=%s,value=%s,local=%s,asdict=%s"
		raise Exception(msg % (key, value, local, asdict))


def config_to_dict(config_lines):
	"""parses the lines from git config --list into a dictionary"""

	newdict = {}
	for line in config_lines:
		k, v = line.split('=')
		k = k.replace('.','_') # git -> model
		if v == 'true' or v == 'false':
			v = bool(eval(v.title()))
		try:
			v = int(eval(v))
		except:
			pass
		newdict[k]=v
	return newdict

def log(oneline=True, all=False):
	'''Returns a pair of parallel arrays listing the revision sha1's
	and commit summaries.'''
	kwargs = {}
	if oneline:
		kwargs['pretty'] = 'oneline'
	revs = []
	summaries = []
	regex = REV_LIST_REGEX
	output = git('log', all=all, **kwargs)
	for line in output.splitlines():
		match = regex.match(line)
		if match:
			revs.append(match.group(1))
			summaries.append(match.group(2))
	return( revs, summaries )

def ls_files():
	"""git ls-files as a list"""
	return git('ls-files').splitlines()

def ls_tree(rev):
	"""Returns a list of(mode, type, sha1, path) tuples."""
	lines = git('ls-tree', rev, r=True).splitlines()
	output = []
	regex = re.compile('^(\d+)\W(\w+)\W(\w+)[ \t]+(.*)$')
	for line in lines:
		match = regex.match(line)
		if match:
			mode = match.group(1)
			objtype = match.group(2)
			sha1 = match.group(3)
			filename = match.group(4)
			output.append((mode, objtype, sha1, filename,) )
	return output

def push(remote, local_branch, remote_branch, ffwd=True, tags=False):
	if ffwd:
		branch_arg = '%s:%s' % ( local_branch, remote_branch )
	else:
		branch_arg = '+%s:%s' % ( local_branch, remote_branch )
	return git('push', remote, branch_arg, with_status=True, tags=tags)

def rebase(newbase):
	if not newbase:
		return 'No base branch specified to rebase.'
	return git('rebase', newbase)

def remote(*args):
	return git('remote', without_stderr=True, *args).splitlines()

def remote_url(name):
	return config('remote.%s.url' % name, local=True)

def reset(to_unstage):
	'''Use 'git reset' to unstage files from the index.'''
	if not to_unstage:
		return 'No files to reset.'

	argv = [ 'reset', '--' ]
	argv.extend(to_unstage)
	return git(*argv)

def rev_list_range(start, end):
	argv = [ 'rev-list', '--pretty=oneline', start, end ]
	raw_revs = git(*argv).splitlines()
	revs = []
	for line in raw_revs:
		match = REV_LIST_REGEX.match(line)
		if match:
			rev_id = match.group(1)
			summary = match.group(2)
			revs.append((rev_id, summary,) )
	return revs

def show(sha1):
	return git('show',sha1)

def show_cdup():
	'''Returns a relative path to the git project root.'''
	return git('rev-parse','--show-cdup')

def status():
	'''RETURNS: A tuple of staged, unstaged and untracked files.
	( array(staged), array(unstaged), array(untracked) )'''

	status_lines = git('status').splitlines()

	unstaged_header_seen = False
	untracked_header_seen = False

	modified_header = '# Changed but not updated:'
	modified_regex = re.compile('(#\tmodified:\s+'
			'|#\tnew file:\s+'
			'|#\tdeleted:\s+)')

	renamed_regex = re.compile('(#\trenamed:\s+)(.*?)\s->\s(.*)')

	untracked_header = '# Untracked files:'
	untracked_regex = re.compile('#\t(.+)')

	staged = []
	unstaged = []
	untracked = []

	# Untracked files
	for status_line in status_lines:
		if untracked_header in status_line:
			untracked_header_seen = True
			continue
		if not untracked_header_seen:
			continue
		match = untracked_regex.match(status_line)
		if match:
			filename = match.group(1)
			untracked.append(filename)

	# Staged, unstaged, and renamed files
	for status_line in status_lines:
		if modified_header in status_line:
			unstaged_header_seen = True
			continue
		match = modified_regex.match(status_line)
		if match:
			tag = match.group(0)
			filename = status_line.replace(tag, '')
			if unstaged_header_seen:
				unstaged.append(filename)
			else:
				staged.append(filename)
			continue
		# Renamed files
		match = renamed_regex.match(status_line)
		if match:
			oldname = match.group(2)
			newname = match.group(3)
			staged.append(oldname)
			staged.append(newname)

	return( staged, unstaged, untracked )

def tag():
	return git('tag').splitlines()