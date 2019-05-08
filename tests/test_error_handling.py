import subprocess as sp

import pytest

from abcmd import Command, error_handler


@pytest.mark.parametrize('args, kwargs, expected', (
    (('cmd', 'err'), {},
     {'command': 'cmd', 'error': 'err', 'rc': None}),

    (('cmd', 'err', 1), {},
     {'command': 'cmd', 'error': 'err', 'rc': 1}),

    ((), {'command': 'cmd', 'error': 'err', 'rc': 1},
     {'command': 'cmd', 'error': 'err', 'rc': 1}),

    (('cmd',), {},
     {'command': 'cmd', 'error': None, 'rc': None}),

    ((), {'error': 'err'},
     {'command': None, 'error': 'err', 'rc': None})
))
def test_error_handler_decorator_arguments(args, kwargs, expected):
    @error_handler(*args, **kwargs)
    def handler(error):
        ...

    attrs = getattr(handler, '_handler', None)

    assert attrs == expected


def test_Command_calls_handle_error_on_subprocess_error():
    handle_list = []

    class MyCommand(Command):
        cat = 'cat NON_EXISTING_FILE'

        def run(self, *args, **kwargs):
            self.cat()

        def handle_error(self, cmd, error):
            handle_list.append(cmd)
            handle_list.append(error)
            return True

    runner = MyCommand({})
    runner()

    assert handle_list == ['cat NON_EXISTING_FILE',
                           'cat: NON_EXISTING_FILE: No such file or directory\n']


def test_Command_stops_if_handle_error_returns_False():
    handle_list = []

    class MyCommand(Command):
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

    runner = MyCommand({})
    with pytest.raises(sp.SubprocessError):
        runner()

    assert handle_list == ['echo']


def test_error_handler_decorator_runs():
    command_flow = []

    def run(cmd):
        return 1, 'out', 'ERROR OUTPUT'

    class MyCommand(Command):
        cmd = 'command with args'

        def run(self, *args, **kwargs):
            self.cmd()

        @error_handler('cmd', 'ERROR OUTPUT')
        def handle_some_error(self, error):
            assert isinstance(self, MyCommand)
            command_flow.append('handle_some_error')
            return True

    runner = MyCommand({}, runner=run)
    runner()

    assert command_flow


def test_CommandRunner_get_error_handlers():
    class MyCommand(Command):
        command = 'command with args'

        def run(self, *args, **kwargs):
            self.command()

        @error_handler('command', 'error0')
        def handler0(self, error):
            ...

        @error_handler('command', 'error1')
        def handler1(self, error):
            ...

        @error_handler('command')
        def handler2(self, error):
            ...

        @error_handler(rc=10)
        def handler3(self, error):
            ...

    runner = MyCommand({})
    command = runner.command

    command.error, command.rc = ('error0', 1)
    handlers = command.get_error_handlers()
    expected_handlers = [MyCommand.handler0, MyCommand.handler2]
    assert sorted(handlers, key=str) == sorted(expected_handlers, key=str)

    command.error, command.rc = ('error1', 1)
    handlers = command.get_error_handlers()
    expected_handlers = [MyCommand.handler1, MyCommand.handler2]
    assert sorted(handlers, key=str) == sorted(expected_handlers, key=str)

    command.error, command.rc = ('error', 10)
    handlers = command.get_error_handlers()
    expected_handlers = [MyCommand.handler2, MyCommand.handler3]
    assert sorted(handlers, key=str) == sorted(expected_handlers, key=str)

    command.error, command.rc = ('error1', 10)
    handlers = command.get_error_handlers()
    expected_handlers = [MyCommand.handler1, MyCommand.handler2, MyCommand.handler3]
    assert sorted(handlers, key=str) == sorted(expected_handlers, key=str)


def test_subclass_inherits_error_handler_decorated_methods():
    command_flow = []

    def run(cmd):
        return 1, 'out', 'ERROR OUTPUT WITH MORE INFO'

    class MyCommand(Command):
        cmd = 'command with args'

        def run(self, *args, **kwargs):
            self.cmd()

        @error_handler('cmd', 'ERROR OUTPUT .*')
        def handle_some_error(self, error):
            assert isinstance(self, MyCommand)
            command_flow.append('handle_some_error')
            return True

    class SubRunner(MyCommand):
        @error_handler('cmd', 'ERROR OUTPUT .*')
        def another_error_handler(self, error):
            command_flow.append('another_error_handler')
            return True

    runner = SubRunner({}, runner=run)
    runner()

    assert ('handle_some_error' in command_flow
            and 'another_error_handler' in command_flow)
