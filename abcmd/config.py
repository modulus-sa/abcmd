"""Mixins for building configurations for commands."""

import abc
import collections
import importlib
import logging
import os
import pprint
import types
from pathlib import Path
from typing import Any, Union, Mapping, MutableMapping, Sequence, Callable, IO

from abcmd import Command


LoadersMappingType = Mapping[str, Union[str, Sequence[str]]]


class MissingConfigurationError(Exception):
    """Raised when a mandatory configuration entry is missing."""


class UnknownFormatError(Exception):
    """Raised when an unsupported configuration file format is encountered."""


# module name - file extensions
DEFAULT_LOADERS = {
    'toml': 'toml',
    'yaml': ('yaml', 'yml'),
    'json': 'json',
}  # type: LoadersMappingType


class ConfigABC(abc.ABC):
    def __init__(self, *args: Mapping[str, Any], **kwargs: Any) -> None:
        if not hasattr(self, 'config'):
            if args and isinstance(args[0], collections.abc.Mapping):
                self.config = args[0]
            else:
                self.config = {}

    def __getitem__(self, name: str) -> Any:
        return self.config[name]


class Loader(ConfigABC):
    """Mixin to load configuration from a file."""

    @staticmethod
    def _find_loaders(default: LoadersMappingType = None) -> Mapping[str, Callable[[IO], Mapping]]:
        if default is None:
            default = DEFAULT_LOADERS
        loaders = {}
        for module_name, extensions in default.items():
            try:
                module = importlib.import_module(module_name)
            except ImportError:
                continue
            if isinstance(extensions, str):
                extensions = [extensions]
            for ext in extensions:
                loaders[ext] = getattr(module, 'load')
        return loaders

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        if not args:
            msg = '{} takes at least on argument'.format(type(self))
            raise TypeError(msg)
        self.task = args[0]
        self.path = args[1] if len(args) > 1 else os.getcwd()
        self.loaders = self._find_loaders()
        self.config = self._load(self.task, self.path)
        super().__init__(*args, **kwargs)

    def _load(self, task: str, path: str) -> Mapping[str, Any]:
        if not os.path.isdir(path):
            raise FileNotFoundError('No such directory: {}'.format(path))

        pathobj = Path(path)
        logging.debug("Searching config files in '{!s}'.".format(pathobj))
        config_files = iter(pathobj.glob(task + '.*'))
        try:
            fname = next(config_files)
        except StopIteration:
            msg = 'Could not find configuration file for task {!r}'
            raise FileNotFoundError(msg.format(task)) from None
        # first character in suffix is the dot '.'
        file_extension = fname.suffix[1:]
        loader = self.loaders.get(file_extension)
        if loader is None:
            raise UnknownFormatError('Could not load configuration file {}, '
                                     'unknown format'.format(fname))
        with fname.open('r') as config_file:
            logging.debug('Loading configuration file %s with %s ', pathobj, file_extension)
            return loader(config_file)


class Checker(ConfigABC):
    """Mixin to validate configuration."""

    def __new__(cls, *args: Any, **kwargs: Any) -> Any:
        valid = {
            name: attr

            for base in reversed(cls.mro())
            if issubclass(base, ConfigABC)
            and not issubclass(base, Command)

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
