import os
import tempfile
from unittest.mock import Mock

from abcmd.config import (BaseConfig, MissingConfigurationError, UnknownFormatError)

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

