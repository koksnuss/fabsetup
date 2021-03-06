# ~*~ coding: utf-8 ~*~
'''Set up and maintain a local or remote (Ubuntu) linux system.'''

import ConfigParser
import os.path
import StringIO
import sys
import os
import re

import fabric.main
import fabric.operations

from os import chmod
from os.path import dirname, isdir, realpath
sys.path.append(dirname(dirname(realpath(__file__))))

from fabric.api import hosts

from Crypto.PublicKey import RSA

import fabsetup
from fabsetup.fabutils import task, needs_packages, needs_repo_fabsetup_custom
from fabsetup.fabutils import run, suggest_localhost, subtask
from fabsetup.fabutils import install_file_legacy, exists
from fabsetup.fabutils import FABSETUP_CUSTOM_DIR, import_fabsetup_custom
from fabsetup.fabutils import FABFILE_DATA_DIR
from fabsetup.utils import flo
from fabsetup.utils import cyan, blue, green, magenta, red
from fabsetup.utils import query_input, query_yes_no
from fabsetup.addons import load_pip_addons, load_repo_addons

import setup  # load tasks from module setup


if not isdir(FABSETUP_CUSTOM_DIR):

    from fabric.api import task

    @task(default=True)
    @needs_repo_fabsetup_custom
    def INIT():
        '''Init repo `~/.fabsetup-custom` with custom tasks and config.'''
        # decorator @needs_repo_fabsetup_custom makes the job
        print(green('Initialization finished\n'))
        fabsetup_custom_dir = FABSETUP_CUSTOM_DIR
        fabric.operations.local(flo('tree {fabsetup_custom_dir}'))
        print('\nList available tasks: ' + blue('fabsetup -l'))
        print('Show details of a task: `fabsetup -d <task>`, eg: ' +
              blue('fabsetup -d new_addon'))

    @task
    @needs_repo_fabsetup_custom
    def setup_desktop():
        '''Run setup tasks to set up a nicely configured desktop pc.'''
        # decorator @needs_repo_fabsetup_custom makes the job
        print('Init completed. Now run this task again.')
        # Next time, the task setup_desktop from
        # ~/.fabsetup-custom/fabfile_/__init__.py will be executed
        # instead

    @task
    @needs_repo_fabsetup_custom
    def setup_webserver():
        '''Run setup tasks to set up a nicely configured webserver.'''
        # decorator @needs_repo_fabsetup_custom makes the job
        print('Init completed. Now run this task again.')
        # Next time, the task setup_webserver from
        # ~/.fabsetup-custom/fabfile_/__init__.py will be executed
        # instead

else:
    _dir = dirname(dirname(__file__)).rsplit('/fabsetup')[0]
    if _dir.endswith('site-packages'):
        _dir = os.path.join(_dir, 'fabsetup')

    @subtask
    def list_tasks():
        '''List available tasks.'''
        fabric.operations.local('cd {_dir} && fab -l'.format(_dir=_dir))

    @subtask
    def fabsetup_version():
        print('fabsetup-%s' % fabsetup.__version__)

    @subtask
    def pip_packages():
        fabric.operations.local('pip2 freeze | grep -i ^fab || true')

    @subtask
    def git_repos():
        for fabsetup_dir, depth in [
                ('~/.fabsetup', 1),
                ('~/.fabsetup-addon-repos', 1),
                ('~/.fabsetup-downloads', 2),
                ('~/.fabsetup-custom', 1)]:
            fabric.operations.local(flo(
                'if [ -d {fabsetup_dir} ]; then '
                'tree --noreport -L {depth} {fabsetup_dir}; else '
                'echo "{fabsetup_dir} does not exist"; fi'))
            print('')

    from fabric.api import task
    from utlz import print_full_name, print_doc1

    @task(default=True)
    @print_full_name(color=magenta, prefix='\n# ', tail='\n')
    @print_doc1
    def info():
        '''List available tasks, pip packages, git repos, and fabsetup version.
        '''
        print('more info: ' + blue('https://github.com/theno/fabsetup'))
        list_tasks()
        pip_packages()
        git_repos()
        fabsetup_version()

    import_fabsetup_custom(globals())


@task
@suggest_localhost
@needs_packages('debian-goodies')  # for command 'checkrestart'
def up():
    '''Update and upgrade all packages of the Debian or Ubuntu OS.'''
    run('sudo apt-get update')
    run('sudo apt-get dist-upgrade')
    run('sudo apt-get autoremove')
    run('sudo checkrestart')
    dfh()
    check_reboot()


def check_reboot():
    print(magenta('Reboot required?'))
    # check file '/var/run/reboot-required', cf. http://askubuntu.com/a/171
    res = run('; '.join([
        "prefix='\\033['; postfix='\\033[0m'",
        "if [ -f /var/run/reboot-required ]",
        'then echo "${prefix}31mReboot required!${postfix}"',
        'else echo "${prefix}32mNope.${postfix}"',
        'fi',
    ]))
    if res:
        fabric.operations.local(flo('echo "{res}"'))  # interpolate res


@task
def reboot():
    '''Reboot the server.'''
    fabric.operations.reboot()


@task
@suggest_localhost
def dfh():
    '''Print used disc space.'''
    run('sudo  df -ih')
    run('sudo  df -h')


def git_name_and_email_or_die():
    config = ConfigParser.ConfigParser()
    filename = os.path.expanduser('~/.gitconfig')
    try:
        with open(filename) as fh:
            gitconfig = fh.readlines()
    except IOError:
        print(red('~/.gitconfig does not exist') + ', run:\n')
        print('    git config --global user.name "Your Name"')
        print('    git config --global user.email "your.email@example.com"')
        sys.exit()

    config.readfp(StringIO.StringIO(''.join([line.lstrip()
                                             for line
                                             in gitconfig])))

    name = None
    email = None
    try:
        name = config.get('user', 'name')
    except ConfigParser.NoOptionError:
        print(red('missing user.name in ~/.gitconfig') + ', run:\n')
        print('    git config --global user.name "Your Name"')
        sys.exit()
    try:
        email = config.get('user', 'email')
    except ConfigParser.NoOptionError:
        print(red('missing user.email in ~/.gitconfig') + ', run:\n')
        print('    git config --global user.email "your.email@example.com"')
        sys.exit()

    return name, email

def git_ssh_or_die(username):
    ''' Check if a ssh-key is created and imported in github. If not die. '''

    # ssh path
    path = os.path.expanduser('~/.ssh/')
    # ssh pub key dictionary
    pub_keys = []

    # check if ~/.ssh exists, if not die
    if not os.path.isdir(path):
        print(red('Could not open folder "~/.ssh". If you do not have a public ssh key, please create one and place it in "~/.ssh/arbitrarykeyname.pub". Please name your public key ".pub" at the end and return to the setup.'))
        exit(1)

    # loop through files in ~/.ssh and search for ssh public keys
    for file in os.listdir(path):
        if re.search("\.pub$", file):                # check if file ends with .pub
            try:
                pub_key = open(path + file, 'r')     # open found *.pub file
                for line in pub_key.readlines():     # loop through lines and append appropriate
                    pub_keys.append(line.split()[1]) # ssh public key if *.pub file is not empty
                pub_key.close()                      # close *.pub file
            except IOError, OSError:        
                print(red('ERROR: Could not read ' + path + file + ' moving on ...'))
    if len(pub_keys) < 1:                            # die if no public ssh key is found
        print(red('ERROR: You do not have a ssh public key. Please create one first and import it into your github account. Then restart this setup.'))
        exit(1)

    # search github pub keys
    github_pub_keys = os.popen(                      # get github pub keys from user
        'curl -s https://github.com/' + username + '.keys').read()
    if github_pub_keys:                              # check if pub key is not empty
        for line in github_pub_keys.splitlines():    # loop through github pub keys and
            line = line.split()                      # append them to pub_keys
            pub_keys.append(line[1])

    # check if matching keys are found
    if len(pub_keys) == len(set(pub_keys)):
        print(red( 'ERROR: Could not find your public key in github. Please import your public key into github and restart the setup.'))
        sys.exit(1)


@subtask
def create_files(
        # '/home/theno/.fabsetup-addon-repos/fabsetup-theno-termdown'
        addon_dir,
        username,   # 'theno'
        addonname,  # 'termdown'
        taskname,   # 'termdown'
        author,
        author_email,
        headline='',
        description='',
        touched_files=''):
    filenames = [
        '.gitignore',
        'fabfile-dev.py',
        'fabfile.py',
        'LICENSE',
        'MANIFEST.in',
        'README.md',
        'requirements.txt',
        'setup.py',
        'fabsetup_USER_TASK/fabutils.py',
        'fabsetup_USER_TASK/__init__.py',
        'fabsetup_USER_TASK/_version.py',
    ]
    for filename in filenames:
        install_file_legacy(
            path=flo('~/.fabsetup-addon-repos/fabsetup-USER-ADDON/{filename}'),
            username=username,
            addonname=addonname,
            taskname=taskname,
            headline=headline,
            description=description,
            touched_files=touched_files,
            author=author,
            author_email=author_email,
            USER=username,
            ADDON=addonname,
            TASK=taskname,
        )

    # avoid substitution of USERNAME in path
    install_file_legacy(
        path='~/.fabsetup-addon-repos/fabsetup-{USER}-{ADDON}/'
             'fabsetup_{USER}_{TASK}/files/home/USERNAME/bin/'
             'termdown.template'.format(USER=username,
                                        ADDON=addonname,
                                        TASK=taskname),
        from_path='~/.fabsetup-addon-repos/fabsetup-USER-ADDON/'
                  'fabsetup_USER_TASK/files/home/USERNAME/bin/'
                  'termdown.template')

    print('')
    fabric.operations.local(flo('tree {addon_dir}'))


@subtask
def init_git_repo(basedir):
    basedir_abs = os.path.expanduser(basedir)
    if os.path.isdir(flo('{basedir_abs}/.git')):
        print('git repo already initialized (skip)')
    else:
        fabric.operations.local(flo('cd {basedir} && git init'))
        fabric.operations.local(flo('cd {basedir} && git add .'))
        fabric.operations.local(
            flo('cd {basedir} && git commit -am "Initial commit"'))


@subtask
def create_github_remote_repo(basedir, github_user, github_repo):
    repo_url = cyan(flo('https://github.com/{github_user}/{github_repo}'))
    question = flo('Create remote repo {repo_url} at github.com?')
    if query_yes_no(question, default='yes'):
        run(flo("cd {basedir}  &&  "
                "curl -u '{github_user}' https://api.github.com/user/repos "
                "-d '") + '{"name":"' + flo('{github_repo}"') + "}'")
        run(flo('cd {basedir}  &&  '
                'git remote add origin '
                'git@github.com:{github_user}/{github_repo}.git'))
        run(flo('cd {basedir}  &&  git push origin master'))
    else:
        print('\nplease, do it yourself:\n'
              '  https://help.github.com/articles/'
              'adding-an-existing-project-to-github-using-the-command-line/')


@subtask
def summary(addon_dir, username, taskname):
    print('run your task:')
    print('')
    print('    # with fabsetup as an addon')
    print('    cd .fabsetup')
    print(flo('    fab -d {username}.{taskname}'))
    print(flo('    fab {username}.{taskname}'))
    print('')
    print('    # standalone')
    print(flo('    cd {addon_dir}'))
    print(flo('    pip2 install -r requirements.txt'))
    print(flo('    fab {username}.{taskname}'))
    print('')
    print('addon development:')
    print('')
    print(flo('    cd {addon_dir}'))
    print('    fab -f fabfile-dev.py -l')
    print('    fab -f fabfile-dev.py test')
    print("    git commit -am 'my commit message'")
    print('    git push origin master  # publish at github')
    print('    fab -f fabfile-dev.py pypi  # publish pip package at pypi')
    print('')
    print('The task code is defined in')
    print(
        cyan(flo('  {addon_dir}/fabsetup_{username}_{taskname}/__init__.py')))
    print('Your task output should be in markdown style.\n')
    print('More infos: '
          'https://github.com/theno/fabsetup/blob/master/howtos/'
          'fabsetup-addon.md')


@task
@hosts('localhost')
def new_addon():
    '''Create a repository for a new fabsetup-task addon.

    The repo will contain the fabsetup addon boilerplate.

    Running this task you have to enter:
    * your github user account (your pypi account should be the same or similar)
    * addon name
    * task name
    * headline, short description, and touched (and created) files and dirs
      for the task docstring and the README.md

    Created files and dirs:

        ~/.fabsetup-addon-repos/fabsetup-{user}-{addon}
                                ├── fabfile-dev.py
                                ├── fabfile.py
                                ├── fabsetup_{user}_{task}
                                │   ├── files
                                │   │   └── home
                                │   │       └── USERNAME
                                │   │           └── bin
                                │   │               └── termdown.template
                                │   ├── __init__.py  <--.
                                │   └── _version.py      `- task definition
                                ├── .git
                                │   ├── ...
                                │   ├── config
                                │   └── ...
                                ├── .gitignore
                                ├── README.md
                                ├── requirements.txt
                                └── setup.py
    '''
    author, author_email = git_name_and_email_or_die()

    username = query_input('github username:')

    git_ssh_or_die(username)

    addonname = query_input('\naddon name:', default='termdown')
    addonname = addonname.replace('_', '-').replace(' ', '-')  # minus only
    full_addonname = flo('fabsetup-{username}-{addonname}')
    print('└─> full addon name: {0}\n'.format(
        cyan(full_addonname)))

    taskname = query_input('task name:', default=addonname.replace('-', '_'))
    taskname = taskname.replace('-', '_').replace(' ', '_')  # underscores only
    print('└─> full task name: {0}'.format(
        cyan(flo('{username}.{taskname}\n'))))

    addon_dir = os.path.expanduser(flo(
        '~/.fabsetup-addon-repos/fabsetup-{username}-{addonname}'))

    if os.path.exists(addon_dir):
        print(red(flo('\n{addon_dir} already exists.')))
        print('abort')
    else:
        print('~/.gitconfig')
        print('├─> author: {0} ─> LICENSE, setup.py'.format(cyan(author)))
        print('└─> author email: {0} ─> setup.py'.format(cyan(author_email)))

        headline = query_input(
            '\nshort task headline:',
            default='Install or update termdown.')

        description = query_input(
            '\ndescribing infos:',
            default='''Termdown (https://github.com/trehn/termdown) is a
    "[c]ountdown timer and stopwatch in your terminal".

    It installs termdown via `pip install --user termdown`.  Also, it installs a
    bash-wrapper script at `~/bin/termdown` which is convenient to time pomodoro
    sessions and pops up a notification when the timer finishes.''')

        touched_files = query_input(
            '\naffected files, dirs, and installed packages:',
            default='~/bin/termdown\n        '
                    'pip-package termdown (`--user` install)')

        print('\naddon git-repository dir: {0}'.format(cyan(addon_dir)))
        if not query_yes_no('\ncreate new addon?', default='yes'):
            print('abort')
        else:
            create_files(addon_dir, username, addonname, taskname,
                         author, author_email,
                         headline, description, touched_files)
            init_git_repo(addon_dir)
            create_github_remote_repo(basedir=addon_dir,
                                      github_user=username,
                                      github_repo=full_addonname)
            summary(addon_dir, username, taskname)


load_pip_addons(globals())
load_repo_addons(globals())
