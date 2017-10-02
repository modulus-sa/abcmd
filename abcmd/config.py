"""Mixins for building configurations for commands."""

import glob
import importlib
import logging
import os
import pprint
import sys
import types

if sys.version_info.minor < 5:
    import collections as cabc
    from .typingstub import Any, Union, Sequence, Mapping, Callable, IO
else:
    import collections.abc as cabc
    from typing import Any, Union, Sequence, Mapping, Callable, IO

if sys.version_info.minor < 3:
    class FileNotFoundError(IOError):
        """For backwards compatibility with python<3.2,
        for more info look at python docs."""


LoadersMappingType = Mapping[str, Union[str, Sequence[str]]]


class MissingConfigurationError(Exception):
    """Raised when a mandatory configuration entry is missing."""


class UnknownFormatError(Exception):
    """Raised when an unsupported configuration file format is encountered."""


# module name - file extensions
DEFAULT_LOADERS = {
    'toml': 'toml',
    'yaml': 'yaml',
    'yml': 'yaml',
    'json': 'json',
}  # type: LoadersMappingType


class ConfigBase:
    def __init__(self, *args: Mapping[str, Any], **kwargs: Any) -> None:
        if not self.__dict__.get('config'):
            if args and isinstance(args[0], cabc.Mapping):
                self.config = args[0]
            else:
                self.config = {}

    def __getitem__(self, key: str) -> Any:
        return self.config[key]

    def __setitem__(self, key, value):
        self.config[key] = value

    def __getattr__(self, attr):
        return getattr(self.config, attr)


class Loader(ConfigBase):
    """Mixin to load configuration from a file."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        if not args:
            msg = '{} takes at least one argument.'
            raise TypeError(msg.format(self.__class__.__name__))
        if not isinstance(args[0], str):
            msg = "first argument of {} must be of type 'str' not '{}'"
            raise TypeError(msg.format(self.__class__.__name__, args[0].__class__.__name__))
        self.task = args[0]
        self.path = args[1] if len(args) > 1 else os.getcwd()
        if not os.path.isdir(self.path):
            raise FileNotFoundError('No such directory: {}'.format(self.path))
        self.config = self._load(self.task, self.path)
        super().__init__(*args, **kwargs)

    @staticmethod
    def _find_loader(extension, default: LoadersMappingType = None) -> Callable[[str], dict]:
        if default is None:
            default = DEFAULT_LOADERS
        try:
            module = importlib.import_module(default[extension])
        except (ImportError, KeyError):
            return None
        else:
            try:
                return getattr(module, 'load')
            except AttributeError:
                return None

    def _load(self, task: str, path: str) -> Mapping[str, Any]:

        logging.debug("Searching config files in '{!s}'.".format(path))
        config_files = iter(glob.glob(os.path.join(path, task + '.*')))
        try:
            fname = next(config_files)
        except StopIteration:
            msg = 'Could not find configuration file for task {!r}'
            raise FileNotFoundError(msg.format(task))
        # first character in suffix is the dot '.'
        file_extension = os.path.splitext(fname)[1][1:]
        logging.debug('Looking for loader for file {!s} '
                      'with extension {!r}'.format(fname, file_extension))
        loader = self._find_loader(file_extension)
        if loader is None:
            msg = ('Could not load configuration file {!s}, '
                   'unknown format {!r}'.format(fname, file_extension))
            logging.error(msg)
            raise UnknownFormatError(msg)
        logging.debug('Found loader: {}'.format(loader))
        with open(fname, 'r') as config_file:
            logging.debug('Loading configuration file {}'.format(fname))
            return loader(config_file)


class Checker(ConfigBase):
    """Mixin to validate configuration."""

    def __new__(cls, *args: Any, **kwargs: Any) -> Any:
        valid = {
            name: attr

            for base in reversed(cls.mro())
            if issubclass(base, ConfigBase)

            for name, attr in vars(base).items()
            if not name.startswith('_')
            and not isinstance(attr, types.FunctionType)
        }
        obj = super().__new__(cls)
        obj.valid = valid
        return obj

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Build the configuration according to validation.

        If there is a missing entry and validation provides an object
        for that entry this object is used as the default value,
        if the validation for that entry is a type a ``MissingConfigError``
        exception is raised. The types of the values in the configuration are
        checked against validation, if there is a type mismatch a ``TypeError``
        is raised."""
        super().__init__(*args, **kwargs)
        # if not hasattr(self, 'valid'):
        #     self.valid = {}  # type: MutableMapping[str, Any]
        self._validate()

    def _validate(self) -> None:
        """Fill config with default entries and validate values."""
        config = self.config  # type: MutableMapping[str, Any]
        logging.debug('Checking config:\n%s', pprint.pformat(config))
        for opt, validator in self.valid.items():
            if opt in config:
                if not isinstance(validator, type):
                    validator = type(validator)
                if not isinstance(config[opt], validator):
                    current_type = type(config[opt])
                    msg = '{!r} must be of type {!r} not {!r}'
                    msg = msg.format(opt, validator.__name__, current_type.__name__)
                    raise TypeError(msg)
            else:
                if not isinstance(validator, type):
                    # default value
                    config[opt] = validator
                else:
                    missing = set(self.valid) - set(config)
                    msg = ('Missing required configuration entries: '
                           '{}'.format(', '.join(missing)))
                    raise MissingConfigurationError(msg)
