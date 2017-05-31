import os
import subprocess as sp
import tempfile
from unittest.mock import Mock

import abcmd
from abcmd import (BaseConfig, CommandFormatter, BaseCommand,
                   MissingConfigurationError, UnknownFormatError,
                   parse_args, log_error_and_exit)

import pytest


@pytest.fixture
def stub_loader():
    class Loader(BaseConfig):
        pass
    return Loader()


@pytest.fixture(params=[
    ('yaml', '---\ntest_entry: ok'),
    ('toml', 'test_entry = "ok"\n'),
])
def config_file(request):
    extension, text = request.param
    with tempfile.NamedTemporaryFile(suffix='.' + extension) as config:
        task = os.path.splitext(os.path.basename(config.name))[0]
        config.write(text.encode())
        config.seek(0)
        yield {'task': task, 'path': os.path.dirname(config.name),
               'file': config.name, 'loader': extension}


def test_BaseConfig_raises_error_on_wrong_path_name(stub_loader):
    with pytest.raises(FileNotFoundError):
        stub_loader('test_task', path='/non/existing/path')


def test_BaseConfig_raises_error_on_wrong_task_name(stub_loader):
    with pytest.raises(FileNotFoundError):
        stub_loader('wrong_test_task_name', path='/tmp')


def test_BaseConfig_raises_error_on_unknown_file_format(stub_loader, tmpdir):
    with tempfile.NamedTemporaryFile(suffix='.unknown_extension') as temp_config:
        temp_config.write(b'')
        task = os.path.splitext(os.path.basename(temp_config.name))[0]

        with pytest.raises(UnknownFormatError):
            stub_loader(task, '/tmp')


def test_BaseConfig_fills_valid_attribute_with_class_attributes():
    class Loader(BaseConfig):
        attr0 = 'attribute 0'
        attr1 = 'attribute 1'

    loader = Loader()

    assert loader._valid == {'attr0': 'attribute 0', 'attr1': 'attribute 1'}


def test_BaseConfig_fills_default_config_if_missing(mocker):
    class Loader(BaseConfig):
        existing = str
        missing = 'default value'

    mocker.patch.object(Loader, '_load').return_value = {'existing': 'existing_value'}

    loader = Loader()
    conf = loader('task')

    assert conf == {'existing': 'existing_value', 'missing': 'default value'}


def test_BaseConfig_complains_on_missing_config(mocker):
    class Loader(BaseConfig):
        existing = str
        missing0 = str
        missing1 = str

    mocker.patch.object(Loader, '_load').return_value = {'test_option': 'string'}

    loader = Loader()

    with pytest.raises(MissingConfigurationError) as err:
        loader('task')
    msg = str(err)
    # missing enries come in random order
    assert "Missing required configuration entries:" in msg
    assert "missing0" in msg
    assert "missing1" in msg


def test_BaseConfig_complains_on_wrong_types(config_file, mocker):
    class Loader(BaseConfig):
        test_option = int

    mocker.patch.object(Loader, '_load').return_value = {'test_option': 'string'}

    loader = Loader()

    with pytest.raises(TypeError) as err:
        loader(config_file['task'], config_file['path'])
    assert str(err).endswith("test_option must be of type 'int' not 'str'")


def test_BaseConfig_complains_on_wrong_types_with_default(config_file, monkeypatch):
    class Loader(BaseConfig):
        test_option = int

    _load_mock = Mock(return_value={'test_option': 'string'})
    monkeypatch.setattr(Loader, '_load', _load_mock)

    loader = Loader()

    with pytest.raises(TypeError) as err:
        loader(config_file['task'], config_file['path'])
    assert str(err).endswith("test_option must be of type 'int' not 'str'")


def test_BaseConfig_okay(config_file, monkeypatch):
    class Loader(BaseConfig):
        test_option0 = str
        test_option1 = int

    conf = {'test_option0': 'string', 'test_option1': 10}
    _load_mock = Mock(return_value=conf)
    monkeypatch.setattr(Loader, '_load', _load_mock)

    loader = Loader()

    config = loader(config_file['task'], config_file['path'])

    assert config == conf


def test_BaseConfig_uses_correct_loader_with_correct_file(stub_loader, config_file, mocker):
    loader_mock = Mock(return_value={})
    mocker.patch.dict(stub_loader._loaders, {config_file['loader']: loader_mock})

    stub_loader(config_file['task'], config_file['path'])

    file_arg = loader_mock.call_args[0][0]

    assert file_arg.name == config_file['file']


def test_load_BaseConfig_with_each_loader(config_file):
    class Loader(BaseConfig):
        test_entry = str

    loader = Loader()
    config = loader(config_file['task'], config_file['path'])

    assert config['test_entry'] == 'ok'


def test_BaseConfig_has_attrs_from_all_baseclasses():
    class FirstLoader(BaseConfig):
        option0 = 0
        option1 = 1
        overriden = 'a'

    class SecondLoader(FirstLoader):
        option2 = 2
        option3 = 3
        overriden = 'b'

    loader = SecondLoader()

    assert loader._valid == {'option0': 0, 'option1': 1,
                             'option2': 2, 'option3': 3,
                             'overriden': 'b'}


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


def test_BaseCommand_abstract_methods():
    assert BaseCommand.__abstractmethods__ == {'run', 'dont_run', 'handle_error'}


def test_BaseCommand_init_arguments():
    class Runner(BaseCommand):
        def dont_run(self):
            return False

        def run(self):
            pass

        def handle_error(self, err):
            pass

    with pytest.raises(TypeError) as err:
        Runner()

    assert str(err).endswith("TypeError: __init__() missing 1 required "
                             "positional argument: 'config'")


def test_BaseCommand_run(monkeypatch):
    call_list = []

    class Runner(BaseCommand):
        def dont_run(self):
            return False

        def run(self):
            call_list.append('run')

        def handle_error(self, err):
            pass

    runner = Runner({})

    runner()

    assert call_list == ['run']


def test_BaseCommand_run_templates(mocker):
    run_cmd_mock = mocker.patch('abcmd.BaseCommand._run_cmd')

    class Runner(BaseCommand):
        template = 'command template {-o OPT}'

        def dont_run(self):
            return False

        def run(self):
            self.run_template()

        def handle_error(self, err):
            pass

    runner = Runner({'OPT': 'argument'})
    runner()

    assert runner.run_template.__name__ == 'run_template'
    run_cmd_mock.assert_called_with('command template -o argument')


def test_BaseCommand_getitem_from_config():
    class Runner(BaseCommand):
        def dont_run(self):
            return True

        def run(self):
            pass

        def handle_error(self, err):
            pass

    runner = Runner({'attr0': 'attribute 0', 'attr1': 'attribute 1'})

    assert runner['attr0'] == 'attribute 0' and runner['attr1'] == 'attribute 1'


def test_BaseCommand_dont_run_prevents_calling_run():
    call_list = []

    class Runner(BaseCommand):
        def dont_run(self):
            return True

        def run(self):
            call_list.append('run')

        def handle_error(self, err):
            pass

    runner = Runner({})
    runner()

    assert call_list == []


def test_BaseCommand_calls_handle_error_on_subprocess_error():
    handle_list = []

    class Runner(BaseCommand):
        cat = 'cat NON_EXISTING_FILE'

        def dont_run(self):
            return False

        def run(self):
            self.run_cat()

        def handle_error(self, cmd, error):
            handle_list.append(cmd)
            handle_list.append(error)
            return True

    runner = Runner({})
    runner()

    assert handle_list == ['cat NON_EXISTING_FILE',
                           'cat: NON_EXISTING_FILE: No such file or directory']


def test_BaseCommand_stops_if_handle_error_returns_False():
    handle_list = []

    class Runner(BaseCommand):
        echo = 'echo HEY'
        cat = 'cat NON_EXISTING_FILE'

        def dont_run(self):
            return False

        def run(self):
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


def test_BaseCommand_caches_templated_functions():
    class Runner(BaseCommand):
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


@pytest.mark.parametrize('cmd, expected', (
    ('testtask -c test_configpath --dry-run',
     {'task': 'testtask', 'configpath': 'test_configpath', 'dry_run': True}),
    ('testtask',
     {'task': 'testtask', 'configpath': '/tmp', 'dry_run': False}),
    ('', {})
))
def test_parse_args(cmd, expected):
    if not cmd:
        with pytest.raises(SystemExit):
            args = parse_args(cmd.split(), confdir='/tmp')
    else:
        args = parse_args(cmd.split(), confdir='/tmp')
        assert vars(args) == expected



@pytest.mark.parametrize('error', (
    TypeError('error message'),
    'error message',
    'error: message'
))
def test_log_error_and_exit(error, mocker):
    exit_mock = mocker.patch('abcmd.sys.exit')
    logging_mock = mocker.patch('abcmd.logging.error')

    log_error_and_exit(error)

    assert logging_mock.called
    assert exit_mock.called
