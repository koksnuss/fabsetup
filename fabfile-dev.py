import sys
from os.path import dirname

from fabric.api import execute, local, task

from utlz import flo, cyan


def query_yes_no(question, default="yes"):
    """Ask a yes/no question via raw_input() and return their answer.

    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
    It must be "yes" (the default), "no", or None (which means an answer
    of the user is required).

    The "answer" return value is True for "yes" or False for "no".
    """
    valid = {"yes": True, "y": True, "ye": True, '1': True,
             "no": False, "n": False, '0': False, }
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        sys.stdout.write(question + prompt)
        choice = raw_input().lower()
        if default is not None and choice == '':
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write("Please respond with 'yes' or 'no' "
                             "(or 'y' or 'n').\n")


@task
def clean():
    '''Delete temporary files not under version control.'''

    basedir = dirname(__file__)

    print(cyan('delete temp files and dirs for packaging'))
    local(flo(
        'rm -rf  '
        '{basedir}/.eggs/  '
        '{basedir}/fabsetup.egg-info/  '
        '{basedir}/dist  '
        '{basedir}/README  '
        '{basedir}/build/  '
    ))

    print(cyan('\ndelete temp files and dirs for editing'))
    local(flo(
        'rm -rf  '
        '{basedir}/.cache  '
        '{basedir}/.ropeproject  '
    ))

    print(cyan('\ndelete bytecode compiled versions of the python src'))
    # cf. http://stackoverflow.com/a/30659970
    local(flo('find  {basedir}/fabsetup  '
              'fabfile*  ') +
          '\( -name \*pyc -o -name \*.pyo -o -name __pycache__ '
          '-o -name \*.so -o -name \*.o -o -name \*.c \) '
          '-prune '
          '-exec rm -rf {} + || true')


@task
def pypi():
    '''Build package and upload to pypi.'''
    if not query_yes_no('version updated in '
                        '`fabsetup/_version.py`?'):
        print('abort')
    else:
        print(cyan('\n## clean-up\n'))
        execute(clean)

        basedir = dirname(__file__)

        # latest_pythons = _determine_latest_pythons()
        # # e.g. highest_minor: '3.6'
        # highest_minor = _highest_minor(latest_pythons)
        # python = flo('python{highest_minor}')
        python = 'python'

        print(cyan('\n## build package'))
        local(flo('cd {basedir}  &&  {python}  setup.py  sdist'))

        print(cyan('\n## upload package'))
        local(flo('cd {basedir}  &&  {python} -m twine upload  dist/*'))
