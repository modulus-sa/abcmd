from abcmd import Command

import pytest


@pytest.fixture()
def run_cmd(mocker):
    return mocker.Mock(return_value=(0, 'out', 'err'))


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
            and runner.template0.name == 'template0'
            and str(runner.template0).startswith('template0 runner'))

    assert (callable(runner.template1)
            and runner.template1.name == 'template1'
            and str(runner.template1).startswith('template1 runner'))


def test_Command_run_templates(mocker, run_cmd):

    class Runner(Command):
        template = 'command template {-o OPT}'

        def run(self, *args, **kwargs):
            self.template()

    runner = Runner({'OPT': 'argument'}, runner=run_cmd)
    runner()

    assert runner.template.name == 'template'
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
