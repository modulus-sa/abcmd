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

    assert str(err).endswith("TypeError: missing configuration.")


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


def test_Command_run_templates(mocker):
    run_cmd_mock = mocker.patch('abcmd.Command._run_cmd')

    class Runner(Command):
        template = 'command template {-o OPT}'

        def dont_run(self):
            return False

        def run(self, *args, **kwargs):
            self.run_template()

        def handle_error(self, err):
            pass

    runner = Runner({'OPT': 'argument'})
    runner()

    assert runner.run_template.__name__ == 'run_template'
    run_cmd_mock.assert_called_with('command template -o argument')


def test_Command_getitem_from_config():
    class Runner(Command):
        def dont_run(self):
            return True

        def run(self):
            pass

        def handle_error(self, err):
            pass

    runner = Runner({'attr0': 'attribute 0', 'attr1': 'attribute 1'})
    runner()

    assert runner['attr0'] == 'attribute 0' and runner['attr1'] == 'attribute 1'


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
            self.run_cat()

        def handle_error(self, cmd, error):
            handle_list.append(cmd)
            handle_list.append(error)
            return True

    runner = Runner({})
    runner()

    assert handle_list == ['cat NON_EXISTING_FILE',
                           'cat: NON_EXISTING_FILE: No such file or directory']


def test_Command_stops_if_handle_error_returns_False():
    handle_list = []

    class Runner(Command):
        echo = 'echo HEY'
        cat = 'cat NON_EXISTING_FILE'

        def dont_run(self):
            return False

        def run(self, *args, **kwargs):
            self.run_echo()
            handle_list.append('echo')
            self.run_cat()
            handle_list.append('cat')
            self.run_echo()
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

    first_function = runner.run_echo
    second_function = runner.run_echo

    assert first_function is second_function
