"""Mixins for building configurations for commands."""

from collections.abc import Callable
from itertools import chain
import importlib
import logging
import os
import pprint
from pathlib import Path


class MissingConfigurationError(Exception):
    """Raised when a mandatory configuration entry is missing."""


class UnknownFormatError(Exception):
    """Raised when an unsupported configuration file format is encountered."""


# module name - extensions
DEFAULT_LOADERS = {'toml': 'toml',
                   'yaml': ('yaml', 'yml')}


class Mixin:
    def __call__(self, config):
        return config


class Loader(Mixin):
    """Mixin to load configuration from a file."""

    def __init__(self):
        loaders = {}
        for module_name, extensions in DEFAULT_LOADERS.items():
            try:
                module = importlib.import_module(module_name)
            except ImportError:
                pass
            else:
                if isinstance(extensions, str):
                    extensions = [extensions]
                for ext in extensions:
                    loaders[ext] = getattr(module, 'load')
        self._loaders = loaders

    def __call__(self, task, path):
        config = self._load(task, path)
        super().__call__(config)
        return config

    def _load(self, task, path):
        if not os.path.isdir(path):
            raise FileNotFoundError('No such directory: {}'.format(path))

        path = Path(path)
        logging.debug("Searching config files in '{!s}'.".format(path))
        config_files = list(path.glob(task + '.*'))
        print("CONFIG FILES:", config_files)
        config_files = iter(config_files)
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
            res = loader(fname)
            return res


class Checker(Mixin):
    """Mixin to validate configuration."""

    def __new__(cls):
        valid = {name: attr for base in chain(reversed(cls.__bases__), (cls,))
                 for name, attr in base.__dict__.items()
                 if not name.startswith('_')}

        obj = super().__new__(cls)
        obj._valid = valid
        return obj

    def __call__(self, *args, **kwargs):
        """Build the configuration according to validation.

        If there is a missing entry and validation provides an object
        for that entry this object is used as the default value,
        if the validation for that entry is a type a ``MissingConfigError``
        exception is raised. The types of the values in the configuration are
        checked against validation, if there is a type mismatch a ``TypeError``
        is raised."""
        config = super().__call__(*args, **kwargs)
        self._validate(config)
        return config

    def _validate(self, config):
        """Fill config with default entries and validate values."""
        logging.debug('Checking config:\n%s', pprint.pformat(config))
        for opt, validator in self._valid.items():
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
                    missing = set(self._valid) - set(config)
                    msg = ('Missing required configuration entries: '
                           '{}'.format(', '.join(missing)))
                    raise MissingConfigurationError(msg)
