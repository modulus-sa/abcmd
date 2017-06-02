import os
import tempfile
from unittest.mock import Mock

from abcmd.config import (Loader, Checker, MissingConfigurationError, UnknownFormatError)

import pytest


@pytest.fixture
def loader_obj():
    class TestLoader(Loader):
        pass
    return TestLoader()


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


def test_Loader_raises_error_on_wrong_path_name(loader_obj):
    loader_obj = Loader()

    with pytest.raises(FileNotFoundError):
        loader_obj('test_task', path='/non/existing/path')


def test_Loader_raises_error_on_wrong_task_name(loader_obj):
    loader_obj = Loader()
    with pytest.raises(FileNotFoundError):
        loader_obj('wrong_test_task_name', path='/tmp')


def test_Loader_raises_error_on_unknown_file_format(loader_obj, tmpdir):
    loader_obj = Loader()

    with tempfile.NamedTemporaryFile(suffix='.unknown_extension') as temp_config:
        temp_config.write(b'')
        task = os.path.splitext(os.path.basename(temp_config.name))[0]

        with pytest.raises(UnknownFormatError):
            loader_obj(task, '/tmp')


def test_Loader_uses_correct_loader_with_correct_file(loader_obj, config_file, mocker):
    class TestLoader(Loader):
        pass

    loader = TestLoader()
    loader_mock = Mock(return_value={})
    mocker.patch.dict(loader._loaders, {config_file['loader']: loader_mock})

    loader(config_file['task'], config_file['path'])

    file_arg = loader_mock.call_args[0][0]
    assert file_arg.name == config_file['file']


def test_Loader_with_each_loader(config_file):
    class TestLoader(Loader):
        test_entry = str

    loader = TestLoader()

    config = loader(config_file['task'], config_file['path'])

    assert config['test_entry'] == 'ok'


def test_Checker_fills_valid_attribute_with_class_attributes():
    class TestChecker(Checker):
        attr0 = 'attribute 0'
        attr1 = 'attribute 1'

    checker = TestChecker()

    assert checker._valid == {'attr0': 'attribute 0', 'attr1': 'attribute 1'}


def test_Checker_fills_default_config_if_missing():
    class TestChecker(Checker):
        existing = str
        missing = 'default value'

    checker = TestChecker()

    config = checker({'existing': 'existing_value'})

    assert config == {'existing': 'existing_value', 'missing': 'default value'}


def test_Checker_complains_on_missing_config():
    class TestChecker(Checker):
        existing = str
        missing0 = str
        missing1 = str

    checker = TestChecker()

    with pytest.raises(MissingConfigurationError) as err:
        checker({'test_option': 'string'})
    msg = str(err)
    # missing enries come in random order
    assert "Missing required configuration entries:" in msg
    assert "missing0" in msg
    assert "missing1" in msg


def test_Checker_complains_on_wrong_types():
    class TestChecker(Checker):
        test_option = int

    checker = TestChecker()

    with pytest.raises(TypeError) as err:
        checker({'test_option': 'string'})
    assert str(err).endswith("test_option must be of type 'int' not 'str'")


def test_Checker_complains_on_wrong_types_with_default():
    class TestChecker(Checker):
        test_option = int

    checker = TestChecker()

    with pytest.raises(TypeError) as err:
        checker({'test_option': 'string'})
    assert str(err).endswith("test_option must be of type 'int' not 'str'")


def test_Checker_okay():
    class TestChecker(Checker):
        test_option0 = str
        test_option1 = int

    checker = TestChecker()

    config = checker({'test_option0': 'string', 'test_option1': 10})

    assert config == {'test_option0': 'string', 'test_option1': 10}


def test_Checker_has_attrs_from_all_baseclasses():
    class FirstChecker(Checker):
        option0 = 0
        option1 = 1
        overriden = 'a'

    class SecondChecker(FirstChecker):
        option2 = 2
        option3 = 3
        overriden = 'b'

    checker = SecondChecker()

    assert checker._valid == {'option0': 0, 'option1': 1,
                              'option2': 2, 'option3': 3,
                              'overriden': 'b'}


def test_Checker_overrides_options_in_right_order():
    class FirstChecker(Checker):
        option = 0
        overriden = 'a'

    class SecondChecker(FirstChecker):
        option = 1
        overriden = 'b'

    class ThirdChecker(SecondChecker):
        overriden = 'c'

    checker = ThirdChecker()

    assert checker._valid == {'option': 1, 'overriden': 'c'}


def test_mixin_inheritance_integration_Checker_Loader(config_file):
    class Config(Checker, Loader):
        option = 'a'

    config = Config()

    res = config(config_file['task'], config_file['path'])

    assert res == {'option': 'a', 'test_entry': 'ok'}


def test_mixin_inheritance_integration_Loader_Checker(config_file):
    class Config(Loader, Checker):
        option = 'a'

    config = Config()

    res = config(config_file['task'], config_file['path'])

    assert res == {'option': 'a', 'test_entry': 'ok'}
