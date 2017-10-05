import subprocess as sp

import abcmd
from abcmd import CommandFormatter, Command

import pytest


@pytest.mark.parametrize('template, config, expected', [
    ('init {REPOSITORY}', {'REPOSITORY': '/test_repo'}, 'init /test_repo'),
    # list parameter must be separated with spaces
    ('create {REPOSITORY}::{ARCHIVE} {PATHS}',
     {'REPOSITORY': '/test_repo', 'ARCHIVE': 'test_archive', 'PATHS': ['path0', 'path1']},
     'create /test_repo::test_archive path0 path1'),
    # boolean parameter must exist if True
    ('create {REPOSITORY}::{ARCHIVE} {PATHS} {VERBOSE}',
     {'REPOSITORY': '/test_repo', 'ARCHIVE': 'test_archive',
      'PATHS': ['test_path'], 'VERBOSE': True},
     'create /test_repo::test_archive test_path --verbose'),
    # boolean parameter has right name
    ('create {REPOSITORY}::{ARCHIVE} {PATHS} {READ_SPECIAL}',
     {'REPOSITORY': '/test_repo', 'ARCHIVE': 'test_archive',
      'PATHS': ['test_path'], 'READ_SPECIAL': True},
     'create /test_repo::test_archive test_path --read-special'),
    # boolean parameter must not exist if False
    ('create {REPOSITORY}::{ARCHIVE} {PATHS} {VERBOSE}',
     {'REPOSITORY': '/test_repo', 'ARCHIVE': 'test_archive',
      'PATHS': ['test_path'], 'VERBOSE': False},
     'create /test_repo::test_archive test_path'),
    # optional non boolean parameter
    ('init {REPOSITORY} {-e ENCRYPTION}',
     {'REPOSITORY': '/test_repo', 'ENCRYPTION': 'keyfile'},
     'init /test_repo -e keyfile'),
    # positional list parameter
    ('command {ARGS}',
     {'ARGS': [1, 2, 3, 4]},
     'command 1 2 3 4'),
    # optional non boolean list parameter
    ('create {REPOSITORY}::{ARCHIVE} {PATHS} {-e EXCLUDE}',
     {'REPOSITORY': '/test_repo', 'ARCHIVE': 'test_archive',
      'PATHS': ['test_path'], 'EXCLUDE': ['/exclude0', '/exclude1']},
     'create /test_repo::test_archive test_path -e /exclude0 -e /exclude1'),
    # optional non boolean EMPTY list parameter
    ('create {REPOSITORY}::{ARCHIVE} {PATHS} {-e EXCLUDE}',
     {'REPOSITORY': '/test_repo', 'ARCHIVE': 'test_archive',
      'PATHS': ['test_path'], 'EXCLUDE': []},
     'create /test_repo::test_archive test_path'),
    # optional non boolean EMPTY string parameter
    ('create {REPOSITORY}::{ARCHIVE} {PATHS} {-C COMPRESSION}',
     {'REPOSITORY': '/test_repo', 'ARCHIVE': 'test_archive',
      'PATHS': ['test_path'], 'COMPRESSION': ''},
     'create /test_repo::test_archive test_path'),
    # handle int parameters
    ('prune {-H KEEP_HOURLY}',
     {'KEEP_HOURLY': 1},
     'prune -H 1'),
    # handle "0" as a non Falsy value
    ('command {-o ARG}',
     {'ARG': 0},
     'command -o 0'),
    # long parameters
    ('prune {--keep-hourly KEEP_HOURLY}',
     {'KEEP_HOURLY': 1},
     'prune --keep-hourly 1'),
    # ingore extra args in format field
    ('command {-o OPTION OPTION2}',
     {'OPTION': 'opt'},
     'command -o opt'),
    # positional argument
    ('command {ARG}', {'ARG': 10}, 'command 10'),
])
def test_CommandFormatter_format(config, template, expected):
    formatter = CommandFormatter(config=config)
    assert formatter(template) == expected


def test_CommandFormatter_caches_commands():
    formatter = CommandFormatter({'OPTION': 'option'})
    first_formatted = formatter('command {-o OPTION}')
    second_formatted = formatter('command {-o OPTION}')

    assert first_formatted is second_formatted


def test_CommandFormatter_on_config_change():
    formatter = CommandFormatter({'OPTION': 'option'})
    assert formatter('command {OPTION}') == 'command option'

    formatter.config['OPTION'] = 'changed'
    assert formatter('command {OPTION}') == 'command changed'


def test_Command_abstract_methods():
    assert Command.__abstractmethods__ == {'run', 'dont_run', 'handle_error'}


def test_Command_init_arguments():
    class Runner(Command):
        def dont_run(self):
            return False

        def run(self):
            pass

        def handle_error(self, err):
            pass

    with pytest.raises(TypeError) as err:
        Runner()

    assert str(err).endswith("__init__() missing 1 required positional argument: 'config'")


def test_Command_run():
    call_list = []

    class Runner(Command):
        def dont_run(self):
            return False

        def run(self, *args, **kwargs):
            call_list.append('run')

        def handle_error(self, err):
            pass

    runner = Runner({})

    runner()

    assert call_list == ['run']


def test_Command_stores_templates_on_creation():
    class Runner(Command):
        template0 = 'command one'
        template1 = 'command two'

        def run(self):
            pass

        def handle_error(self):
            pass

        def dont_run(self):
            pass

    runner = Runner({})

    assert runner._templates == {'template0': 'command one',
                                 'template1': 'command two'}

def test_Command_run_templates(mocker):
    run_cmd_mock = mocker.Mock()

    class Runner(Command):
        template = 'command template {-o OPT}'

        def dont_run(self):
            return False

        def run(self, *args, **kwargs):
            self.template()

        def handle_error(self, err):
            pass

    runner = Runner({'OPT': 'argument'}, runner=run_cmd_mock)
    runner()

    assert runner.template.__name__ == 'template'
    run_cmd_mock.assert_called_with(runner, 'command template -o argument')


def test_Command_dont_run_prevents_calling_run():
    call_list = []

    class Runner(Command):
        def dont_run(self):
            return True

        def run(self):
            call_list.append('run')

        def handle_error(self, err):
            pass

    runner = Runner({})
    runner()

    assert call_list == []


def test_Command_calls_handle_error_on_subprocess_error():
    handle_list = []

    class Runner(Command):
        cat = 'cat NON_EXISTING_FILE'

        def dont_run(self):
            return False

        def run(self, *args, **kwargs):
            self.cat()

        def handle_error(self, cmd, error):
            handle_list.append(cmd)
            handle_list.append(error)
            return True

    runner = Runner({})
    runner()

    assert handle_list == ['cat NON_EXISTING_FILE',
                           'cat: NON_EXISTING_FILE: No such file or directory\n']


def test_Command_stops_if_handle_error_returns_False():
    handle_list = []

    class Runner(Command):
        echo = 'echo HEY'
        cat = 'cat NON_EXISTING_FILE'

        def dont_run(self):
            return False

        def run(self, *args, **kwargs):
            self.echo()
            handle_list.append('echo')
            self.cat()
            handle_list.append('cat')
            self.echo()
            handle_list.append('echo')

        def handle_error(self, cmd, error):
            return False

    runner = Runner({})
    with pytest.raises(sp.SubprocessError):
        runner()

    assert handle_list == ['echo']


def test_Command_caches_templated_functions():
    class Runner(Command):
        echo = 'echo HEY'

        def dont_run(self):
            return False

        def run(self):
            pass

        def handle_error(self, *args):
            pass

    runner = Runner({})

    first_function = runner.echo
    second_function = runner.echo

    assert first_function is second_function


def test_Command_on_config_change_clears_caches():
    command_stream = []

    def run(runner, cmd):
        command_stream.append(cmd)

    class Runner(Command):
        cmd = 'command {OPTION}'

        def dont_run(self):
            return False

        def run(self):
            self.cmd()

        def handle_error(self, *args):
            pass

    runner = Runner({'OPTION': 'option'}, runner=run)
    runner()
    assert command_stream[-1] == 'command option'

    runner.config['OPTION'] = 'changed'
    runner()
    assert command_stream[-1] == 'command changed'


def test_Command_runs_run_before_and_run_after_if_they_are_defined():
    command_stream = []

    class Runner(Command):
        cmd = 'command {OPTION}'

        def before_run(self):
            command_stream.append('before')

        def after_run(self):
            command_stream.append('after')

        def dont_run(self):
            return False

        def run(self):
            pass

        def handle_error(self, *args):
            pass

    runner = Runner({})
    runner()

    assert command_stream == ['before', 'after']
