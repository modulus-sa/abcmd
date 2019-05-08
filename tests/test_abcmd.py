from abcmd import Command

import pytest


@pytest.fixture()
def run_cmd(mocker):
    return mocker.Mock(return_value=(0, 'out', 'err'))


def test_Command_init_arguments():
    class MyCommand(Command):
        def run(self):
            pass

    with pytest.raises(TypeError) as err:
        MyCommand()

    assert str(err).endswith("__init__() missing 1 required positional argument: 'config'")


def test_Command_run():
    call_list = []

    class MyCommand(Command):
        def run(self, *args, **kwargs):
            call_list.append('run')

    command = MyCommand({})

    command()

    assert call_list == ['run']


def test_Command_creates_callables_and_proper_naming():
    class MyCommand(Command):
        attribute0 = 'command one'
        attribute1 = 'command two'

        def run(self):
            pass

    command = MyCommand({})

    assert callable(command.attribute0)
    assert command.attribute0.name == 'attribute0'
    assert repr(command.attribute0).startswith('attribute0 runner')
    assert str(command.attribute0) == 'command one'

    assert callable(command.attribute1)
    assert command.attribute1.name == 'attribute1'
    assert repr(command.attribute1).startswith('attribute1 runner')
    assert str(command.attribute1) == 'command two'


def test_Command_run_attributes(mocker, run_cmd):

    class MyCommand(Command):
        attribute = 'command attribute {-o OPT}'

        def run(self, *args, **kwargs):
            self.attribute()

    command = MyCommand({'OPT': 'argument'}, runner=run_cmd)
    command()

    assert command.attribute.name == 'attribute'
    run_cmd.assert_called_with('command attribute -o argument')


def test_Command_dont_run_prevents_calling_run():
    call_list = []

    class MyCommand(Command):
        def run(self):
            call_list.append('run')

        def dont_run(self):
            return True

    command = MyCommand({})
    command()

    assert call_list == []


def test_Command_caches_attributed_functions():
    class MyCommand(Command):
        echo = 'echo HEY'

        def run(self):
            pass

    command = MyCommand({})

    first_function = command.echo
    second_function = command.echo
    third_function = command.echo

    assert first_function is second_function is third_function


def test_Command_on_config_change_clears_caches():
    command_stream = []

    def run(cmd):
        command_stream.append(cmd)
        return 0, 'out', 'err'

    class MyCommand(Command):
        command = 'command {OPTION}'

        def run(self):
            self.command()

    command = MyCommand({'OPTION': 'option'}, runner=run)
    command()
    assert command_stream.pop() == 'command option'

    command.config['OPTION'] = 'changed'
    command()
    assert command_stream.pop() == 'command changed'


def test_Command_runs_run_before_and_run_after_if_they_are_defined():
    command_stream = []

    class MyCommand(Command):
        cmd = 'command {OPTION}'

        def before_run(self):
            command_stream.append('before')

        def after_run(self):
            command_stream.append('after')

        def run(self):
            pass

    command = MyCommand({})
    command()

    assert command_stream == ['before', 'after']


def test_Command_subclassing_keeps_attributes_from_all_parent_classes():

    class FirstRunner(Command):
        command_first = 'first'
        command_overwrite = 'first overwrite'

        def run(self):
            pass

    class SecondRunner(FirstRunner):
        command_second = 'second'
        command_overwrite = 'second overwrite'

    command = SecondRunner({})

    attrs = ('command_first', 'command_second', 'command_overwrite')
    for attr in attrs:
        assert callable(getattr(command, attr))


def test_Command_instantiated_more_times(run_cmd):
    class MyCommand(Command):
        attribute = 'command attribute {-o OPT}'

        def run(self, *args, **kwargs):
            self.attribute()

    command0 = MyCommand({'OPT': 'argument'}, runner=run_cmd)
    command0()

    run_cmd.assert_called_with('command attribute -o argument')

    command1 = MyCommand({'OPT': 'argument'}, runner=run_cmd)
    command1()

    run_cmd.assert_called_with('command attribute -o argument')


def test_Command_subclassing_with_overwriting_attributes_as_methods_and_calling_super():
    command_stream = []

    def run(cmd):
        command_stream.append(cmd)
        return 0, 'out', 'err'

    class MyCommand(Command):
        attribute = 'command {OPTION}'

        def run(self, *args, **kwargs):
            self.attribute()

    class SubCommand(MyCommand):
        def attribute(self):
            command_stream.append('subcommand attribute start')
            super().attribute()
            command_stream.append('subcommand attribute end')

    command = SubCommand({'OPTION': 'OK'}, runner=run)
    command()
    command()

    assert command_stream == ['subcommand attribute start',
                              'command OK',
                              'subcommand attribute end',
                              'subcommand attribute start',
                              'command OK',
                              'subcommand attribute end']
