import os
import tempfile
from unittest.mock import Mock

from abcmd.config import (Loader, Checker, MissingConfigurationError, UnknownFormatError)

import pytest


@pytest.fixture
def loader():
    class TestLoader(Loader):
        pass

    return TestLoader


def test_Loader_raises_error_on_wrong_path_name(loader):

    with pytest.raises(FileNotFoundError):
        loader('test_task', '/non/existing/path')


def test_Loader_raises_error_on_wrong_task_name(loader):
    with pytest.raises(FileNotFoundError):
        loader('wrong_test_task_name', '/tmp')


def test_Loader_raises_error_on_unknown_file_format(loader, tmpdir):

    with tempfile.NamedTemporaryFile(suffix='.unknown_extension') as temp_config:
        temp_config.write(b'')
        task = os.path.splitext(os.path.basename(temp_config.name))[0]

        with pytest.raises(UnknownFormatError):
            loader(task, '/tmp')


def test_Loader_uses_correct_loader_with_correct_file(loader, config_file, mocker):

    loader_mock = Mock(return_value={})
    mocker.patch.dict(loader._loaders, {config_file['loader']: loader_mock})

    loader(config_file['task'], config_file['path'])

    file_arg = loader_mock.call_args[0][0]
    assert file_arg.name == config_file['file']


def test_Loader_with_each_loader(loader, config_file):

    loader_obj = loader(config_file['task'], config_file['path'])

    print("LOADER OBJ:", loader_obj)

    assert loader_obj.config['test_entry'] == 'ok'


def test_Checker_fills_valid_attribute_with_class_attributes():
    class TestChecker(Checker):
        attr0 = 'attribute 0'
        attr1 = 'attribute 1'

    checker = TestChecker({})

    assert checker.valid == {'attr0': 'attribute 0', 'attr1': 'attribute 1'}


def test_Checker_fills_default_config_if_missing():
    class TestChecker(Checker):
        existing = str
        missing = 'default value'

    checker = TestChecker({'existing': 'existing_value'})

    assert checker.config == {'existing': 'existing_value', 'missing': 'default value'}


def test_Checker_complains_on_missing_config():
    class TestChecker(Checker):
        existing = str
        missing0 = str
        missing1 = str

    with pytest.raises(MissingConfigurationError) as err:
        TestChecker({'test_option': 'string'})
    msg = str(err)
    # missing enries come in random order
    assert "Missing required configuration entries:" in msg
    assert "missing0" in msg
    assert "missing1" in msg


def test_Checker_complains_on_wrong_types():
    class TestChecker(Checker):
        test_option = int

    with pytest.raises(TypeError) as err:
        TestChecker({'test_option': 'string'})
    assert str(err).endswith("test_option must be of type 'int' not 'str'")


def test_Checker_complains_on_wrong_types_with_default():
    class TestChecker(Checker):
        test_option = int

    with pytest.raises(TypeError) as err:
        TestChecker({'test_option': 'string'})
    assert str(err).endswith("test_option must be of type 'int' not 'str'")


def test_Checker_okay():
    class TestChecker(Checker):
        test_option0 = str
        test_option1 = int


    checker = TestChecker({'test_option0': 'string', 'test_option1': 10})

    assert checker.config == {'test_option0': 'string', 'test_option1': 10}


def test_Checker_has_attrs_from_all_baseclasses():
    class FirstChecker(Checker):
        option0 = 0
        option1 = 1
        overriden = 'a'

    class SecondChecker(FirstChecker):
        option2 = 2
        option3 = 3
        overriden = 'b'

    checker = SecondChecker({})

    assert checker.valid == {'option0': 0, 'option1': 1,
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

    checker = ThirdChecker({})

    assert checker.valid == {'option': 1, 'overriden': 'c'}


def test_mixin_inheritance_integration_Checker_Loader(config_file):
    class Config(Checker, Loader):
        option = 'a'

    config = Config(config_file['task'], config_file['path'])

    assert config.config == {'option': 'a', 'test_entry': 'ok'}


def test_mixin_inheritance_integration_Loader_Checker(config_file):
    class Config(Loader, Checker):
        option = 'a'

    config = Config(config_file['task'], config_file['path'])

    assert config.config == {'option': 'a', 'test_entry': 'ok'}


def test_Config_getitem():
    class Config(Checker):
        option = 'a'

    config = Config({})

    assert config['option'] == 'a'


def test_mixin_Loader_Checker_fills_default_values(config_file):
    class Config(Loader, Checker):
        option = 'a'

    config = Config(config_file['task'], config_file['path'])

    assert config['option'] == 'a' and config['test_entry'] == 'ok'


def test_mixin_Checker_Loader_fills_default_values(config_file):
    class Config(Checker, Loader):
        option = 'a'

    config = Config(config_file['task'], config_file['path'])

    assert config['option'] == 'a' and config['test_entry'] == 'ok'
