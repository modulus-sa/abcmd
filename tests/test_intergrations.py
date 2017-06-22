from abcmd import BaseCommand
from abcmd.config import Checker, Loader


def test_Config_mixin_doesnt_pick_BaseCommand_subclass_attributes():
    class Config(Checker):
        opt0 = 'option 0'

    class Cmd(BaseCommand, Config):
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

    class Cmd(BaseCommand, Config):
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

    class Cmd(BaseCommand, SecondConfig):
        cmd = 'echo ok'

        def run(self, *args, **kwargs):
            pass

        def dont_run(self, *args, **kwargs):
            pass

        def handle_error(self, *args, **kwargs):
            pass

    cmd = Cmd(config_file['task'], config_file['path'])

    assert  cmd.valid == {'option_first': 10, 'option_second': 20}
