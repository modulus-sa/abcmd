"""Mixins for building configurations for commands."""

import abc
import importlib
import logging
import os
import pprint
from pathlib import Path

from abcmd import BaseCommand


class MissingConfigurationError(Exception):
    """Raised when a mandatory configuration entry is missing."""


class UnknownFormatError(Exception):
    """Raised when an unsupported configuration file format is encountered."""


# module name - extensions
DEFAULT_LOADERS = {'toml': 'toml',
                   'yaml': ('yaml', 'yml')}


class BaseConfig(abc.ABC):
    def __init__(self, *args, **kwargs):
        if not hasattr(self, 'config'):
            if args and isinstance(args[0], dict):
                self.config = args[0]
            else:
                self.config = {}

    def __getitem__(self, name):
        return self.config[name]


class Loader(BaseConfig):
    """Mixin to load configuration from a file."""

    _loaders = {}
    for _module_name, _extensions in DEFAULT_LOADERS.items():
        try:
            _module = importlib.import_module(_module_name)
        except ImportError:
            pass
        else:
            if isinstance(_extensions, str):
                _extensions = [_extensions]
            for _ext in _extensions:
                _loaders[_ext] = getattr(_module, 'load')

    def __init__(self, *args, **kwargs):
        self.task = args[0]
        self.path = args[1]
        self.config = self._load(self.task, self.path)
        super().__init__(*args, **kwargs)

    def _load(self, task, path):
        if not os.path.isdir(path):
            raise FileNotFoundError('No such directory: {}'.format(path))

        path = Path(path)
        logging.debug("Searching config files in '{!s}'.".format(path))
        config_files = iter(path.glob(task + '.*'))
        try:
            fname = next(config_files)
        except StopIteration:
            raise FileNotFoundError('Could not find configuration '
                                    'file for task {!r}'.format(task))
        # first character in suffix is the dot '.'
        file_extension = fname.suffix[1:]
        loader = self._loaders.get(file_extension)
        if loader is None:
            raise UnknownFormatError('Could not load configuration file {}, '
                                     'unknown format'.format(fname))
        with fname.open('r') as fname:
            logging.debug('Loading configuration %s with %s ', path, file_extension)
            return loader(fname)


class Checker(BaseConfig):
    """Mixin to validate configuration."""

    def __new__(cls, *args, **kwargs):
        valid = {
            name: attr

            for base in reversed(cls.mro())
            if issubclass(base, BaseConfig)
            and not issubclass(base, BaseCommand)

            for name, attr in vars(base).items()
            if not name.startswith('_')
        }
        obj = super().__new__(cls)
        obj.valid = valid
        return obj

    def __init__(self, *args, **kwargs):
        """Build the configuration according to validation.

        If there is a missing entry and validation provides an object
        for that entry this object is used as the default value,
        if the validation for that entry is a type a ``MissingConfigError``
        exception is raised. The types of the values in the configuration are
        checked against validation, if there is a type mismatch a ``TypeError``
        is raised."""
        super().__init__(*args, **kwargs)
        self._validate()

    def _validate(self):
        """Fill config with default entries and validate values."""
        config = self.config
        logging.debug('Checking config:\n%s', pprint.pformat(config))
        for opt, validator in self.valid.items():
            if opt in config:
                if not isinstance(validator, type):
                    validator = type(validator)
                if not isinstance(config[opt], validator):
                    current_type = type(config[opt])
                    msg = '{} must be of type {!r} not {!r}'
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
