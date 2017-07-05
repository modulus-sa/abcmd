import pytest

from abcmd import Command
from abcmd.config import Checker, Loader, MissingConfigurationError


def test_Config_mixin_doesnt_pick_Command_subclass_attributes():
    class Config(Checker):
        opt0 = 'option 0'

    class Cmd(Command, Config):
        cmd = 'cmd'

        def run(self, *args, **kwargs):
            pass

        def dont_run(self, *args, **kwargs):
            pass

        def handle_error(self, *args, **kwargs):
            pass

    runner = Cmd({})
    runner()

    assert runner.valid == {'opt0': 'option 0'}
    assert runner.cmd == 'cmd'


def test_init_calls_all_parents_init(config_file):
    called = []

    class Config(Loader, Checker):
        opt0 = 'option 0'

        def __init__(self, *args, **kwargs):
            called.append(True)
            super().__init__(*args, **kwargs)

    class Cmd(Command, Config):
        cmd = 'cmd'

        def run(self, *args, **kwargs):
            pass

        def dont_run(self, *args, **kwargs):
            pass

        def handle_error(self, *args, **kwargs):
            pass

    runner = Cmd(config_file['task'], config_file['path'])
    runner()

    assert runner.valid == {'opt0': 'option 0'}
    assert runner.cmd == 'cmd'
    assert called == [True]


def test_Config_multi_inheritance_with_command_gets_right_valid_attr(config_file):
    class FirstConfig(Checker, Loader):
        option_first = 10

    class SecondConfig(FirstConfig):
        option_second = 20

    class Cmd(Command, SecondConfig):
        cmd = 'echo ok'

        def run(self, *args, **kwargs):
            pass

        def dont_run(self, *args, **kwargs):
            pass

        def handle_error(self, *args, **kwargs):
            pass

    cmd = Cmd(config_file['task'], config_file['path'])

    assert  cmd.valid == {'option_first': 10, 'option_second': 20}


def test_Command_with_only_Loader(config_file):
    class Cmd(Command, Loader):
        cmd = 'echo ok'

        def run(self, *args, **kwargs):
            pass

        def dont_run(self, *args, **kwargs):
            pass

        def handle_error(self, *args, **kwargs):
            pass

    cmd = Cmd(config_file['task'], config_file['path'])

    assert cmd.config == {'test_entry': 'ok'}


def test_Command_with_only_Checker():
    class Config(Checker):
        opt_int = int
        opt_int = str
        opt_default = 'ok'

    class Cmd(Command, Config):
        cmd = 'echo ok'

        def run(self, *args, **kwargs):
            pass

        def dont_run(self, *args, **kwargs):
            pass

        def handle_error(self, *args, **kwargs):
            pass

    with pytest.raises(MissingConfigurationError):
        Cmd({})
