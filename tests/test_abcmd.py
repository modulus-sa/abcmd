import subprocess as sp

import abcmd
from abcmd import CommandFormatter, Command, error_handler

import pytest


@pytest.fixture()
def run_cmd(mocker):
    return mocker.Mock(return_value=(0, 'out', 'err'))


@pytest.mark.parametrize('template, config, expected', [
    ('cmd {option0}', {'option0': 'test_option'}, 'cmd test_option'),
    # list parameter must be separated with spaces
    ('command {option0}::{option1} {option2}',
     {'option0': 'test_option', 'option1': 'test_option1', 'option2': ['path0', 'path1']},
     'command test_option::test_option1 path0 path1'),
    # boolean parameter must exist if true
    ('command {option0}::{option1} {option2} {verbose}',
     {'option0': 'test_option', 'option1': 'test_option1',
      'option2': ['test_path'], 'verbose': True},
     'command test_option::test_option1 test_path --verbose'),
    # boolean parameter has right name
    ('command {option0}::{option1} {option2} {bool_option}',
     {'option0': 'test_option', 'option1': 'test_option1',
      'option2': ['test_path'], 'bool_option': True},
     'command test_option::test_option1 test_path --bool-option'),
    # boolean parameter must not exist if false
    ('command {option0}::{option1} {option2} {verbose}',
     {'option0': 'test_option', 'option1': 'test_option1',
      'option2': ['test_path'], 'verbose': False},
     'command test_option::test_option1 test_path'),
    # optional non boolean parameter
    ('init {option0} {-e option1}',
     {'option0': 'test_option', 'option1': 'keyfile'},
     'init test_option -e keyfile'),
    # positional list parameter
    ('command {args}',
     {'args': [1, 2, 3, 4]},
     'command 1 2 3 4'),
    # optional non boolean list parameter
    ('command {option0}::{option1} {option2} {-e list_option}',
     {'option0': 'test_option', 'option1': 'test_option1',
      'option2': ['test_path'], 'list_option': ['/list_option0', '/list_option1']},
     'command test_option::test_option1 test_path -e /list_option0 -e /list_option1'),
    # optional non boolean empty list parameter
    ('command {option0}::{option1} {option2} {-e list_option}',
     {'option0': 'test_option', 'option1': 'test_option1',
      'option2': ['test_path'], 'list_option': []},
     'command test_option::test_option1 test_path'),
    # optional non boolean empty string parameter
    ('command {option0}::{option1} {option2} {-c empty_option}',
     {'option0': 'test_option', 'option1': 'test_option1',
      'option2': ['test_path'], 'empty_option': ''},
     'command test_option::test_option1 test_path'),
    # handle int parameters
    ('command {-h keep_hourly}',
     {'keep_hourly': 1},
     'command -h 1'),
    # handle "0" as a non falsy value
    ('command {-o arg}',
     {'arg': 0},
     'command -o 0'),
    # long parameters
    ('command {--long long_option}',
     {'long_option': 1},
     'command --long 1'),
    # long parameters list
    ('command {--long long_option}',
     {'long_option': [1, 2, 3]},
     'command --long 1 --long 2 --long 3'),
    # ingore extra args in format field
    ('command {-o option option2}',
     {'option': 'opt'},
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


def test_Command_init_arguments():
    class Runner(Command):
        def run(self):
            pass


    with pytest.raises(TypeError) as err:
        Runner()

    assert str(err).endswith("__init__() missing 1 required positional argument: 'config'")


def test_Command_run():
    call_list = []

    class Runner(Command):
        def run(self, *args, **kwargs):
            call_list.append('run')

    runner = Runner({})

    runner()

    assert call_list == ['run']


def test_Command_creates_callables_and_proper_naming():
    class Runner(Command):
        template0 = 'command one'
        template1 = 'command two'

        def run(self):
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

        def run(self, *args, **kwargs):
            self.template()

    runner = Runner({'OPT': 'argument'}, runner=run_cmd)
    runner()

    assert runner.template.__name__ == 'template'
    run_cmd.assert_called_with('command template -o argument')


def test_Command_dont_run_prevents_calling_run():
    call_list = []

    class Runner(Command):
        def run(self):
            call_list.append('run')

        def dont_run(self):
            return True

    runner = Runner({})
    runner()

    assert call_list == []


def test_Command_calls_handle_error_on_subprocess_error():
    handle_list = []

    class Runner(Command):
        cat = 'cat NON_EXISTING_FILE'

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

        def run(self):
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

        def run(self):
            self.command()

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

        def run(self):
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

        def run(self, *args, **kwargs):
            self.template()

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

        def run(self, *args, **kwargs):
            self.template()

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


def test_error_handler_decorator():
    command_flow = []

    def run(cmd):
        return 1, 'out', 'ERROR OUTPUT'

    class Runner(Command):
        cmd = 'command with args'

        def run(self, *args, **kwargs):
           self.cmd()

        @error_handler('command', 'ERROR OUTPUT')
        def handle_some_error(self, error):
            assert isinstance(self, Runner)
            command_flow.append('handle_some_error')
            return True

    runner = Runner({}, runner=run)
    runner()

    assert command_flow
