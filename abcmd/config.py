"""Mixins for building configurations for commands."""

import logging
import os
import pprint
from pathlib import Path


class MissingConfigurationError(Exception):
    """Raised when a mandatory configuration entry is missing."""


class UnknownFormatError(Exception):
    """Raised when an unsupported configuration file format is encountered."""


class BaseConfig:
    """Base class for creating custom configuration objects."""

    def __new__(cls):
        valid = {name: attr for base in cls.__bases__ + (cls,)
                 for name, attr in base.__dict__.items()
                 if not name.startswith('_')}

        obj = super().__new__(cls)
        obj._valid = valid
        return obj

    def __init__(self):
        loaders = {}
        try:
            import toml
        except ImportError:
            pass
        else:
            loaders['toml'] = toml.load

        try:
            import yaml
        except ImportError:
            pass
        else:
            loaders['yaml'] = loaders['yml'] = yaml.load

        self._loaders = loaders

    def __call__(self, task, path=None):
        """Build the configuration according to validation.

        If there is a missing entry and validation provides an object
        for that entry this object is used as the default value,
        if the validation for that entry is a type a ``MissingConfigError``
        exception is raised. The types of the values in the configuration are
        checked against validation, if there is a type mismatch a ``TypeError``
        is raised.

        Parameters
        ----------
        task: str
            the name of the task (name of config file without extension)
        path: str
            the path where the configuration file exists
        """
        if path is None:
            path = '.'
        config = self._load(task, path)
        self._validate(config)
        return config

    def _load(self, task, path):
        if not os.path.isdir(path):
            raise FileNotFoundError('No such directory: {}'.format(path))

        path = Path(path)
        logging.debug("Searching config files in '{!s}'.".format(path))
        config_files = list(path.glob(task + '.*'))
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
