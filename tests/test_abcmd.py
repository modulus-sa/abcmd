import subprocess as sp

import abcmd
from abcmd import CommandFormatter, Command

import pytest


@pytest.fixture()
def run_cmd(mocker):
    return mocker.Mock(return_value=(0, 'out', 'err'))


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

    class Runner(Command):
        pass

    with pytest.raises(TypeError):
        runner = Runner({})


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


def test_Command_creates_callables_and_proper_naming():
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

    assert (callable(runner.template0)
            and runner.template0.__name__ == 'template0'
            and str(runner.template0).startswith('template0 runner'))

    assert (callable(runner.template1)
            and runner.template1.__name__ == 'template1'
            and str(runner.template1).startswith('template1 runner'))


def test_Command_run_templates(mocker, run_cmd):

    class Runner(Command):
        template = 'command template {-o OPT}'

        def dont_run(self):
            return False

        def run(self, *args, **kwargs):
            self.template()

        def handle_error(self, err):
            pass

    runner = Runner({'OPT': 'argument'}, runner=run_cmd)
    runner()

    assert runner.template.__name__ == 'template'
    run_cmd.assert_called_with('command template -o argument')


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
    third_function = runner.echo

    assert first_function is second_function is third_function


def test_Command_on_config_change_clears_caches():
    command_stream = []

    def run(cmd):
        command_stream.append(cmd)
        return 0, 'out', 'err'

    class Runner(Command):
        command = 'command {OPTION}'

        def dont_run(self):
            return False

        def run(self):
            self.command()

        def handle_error(self, *args):
            pass

    runner = Runner({'OPTION': 'option'}, runner=run)
    runner()
    assert command_stream.pop() == 'command option'

    runner.config['OPTION'] = 'changed'
    runner()
    assert command_stream.pop() == 'command changed'


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


def test_Command_subclassing_keeps_templates_from_all_parent_classes():

    class FirstRunner(Command):
        command_first = 'first'
        command_overwrite = 'first overwrite'

        def run(self):
            pass

        def dont_run(self):
            pass

        def handle_error(self):
            pass

    class SecondRunner(FirstRunner):
        command_second = 'second'
        command_overwrite = 'second overwrite'

    runner = SecondRunner({})

    attrs = ('command_first', 'command_second', 'command_overwrite')
    for attr in attrs:
        assert callable(getattr(runner, attr))


def test_Command_instantiated_more_times(run_cmd):
    class Runner(Command):
        template = 'command template {-o OPT}'

        def dont_run(self):
            return False

        def run(self, *args, **kwargs):
            self.template()

        def handle_error(self, err):
            pass

    runner0 = Runner({'OPT': 'argument'}, runner=run_cmd)
    runner0()


    run_cmd.assert_called_with('command template -o argument')


    runner1 = Runner({'OPT': 'argument'}, runner=run_cmd)
    runner1()

    run_cmd.assert_called_with('command template -o argument')


def test_Command_subclassing_with_overwriting_templates_as_methods_and_calling_super():
    command_stream = []

    def run(cmd):
        command_stream.append(cmd)
        return 0, 'out', 'err'

    class Runner(Command):
        template = 'command {OPTION}'

        def dont_run(self):
            return False

        def run(self, *args, **kwargs):
            self.template()

        def handle_error(self, err):
            pass

    class SubRunner(Runner):
        def template(self):
            command_stream.append('subrunner template start')
            super().template()
            command_stream.append('subrunner template end')

    runner = SubRunner({'OPTION': 'OK'}, runner=run)
    runner()
    runner()

    assert command_stream == ['subrunner template start',
                              'command OK',
                              'subrunner template end',
                              'subrunner template start',
                              'command OK',
                              'subrunner template end']
