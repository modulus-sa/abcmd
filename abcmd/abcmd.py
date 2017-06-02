"""Abstract Classes to create cli command wrappers that are configured
statically with a file."""

import abc
import shlex
import smtplib
import subprocess as sp
from collections.abc import Iterable
from functools import lru_cache
from string import Formatter
import logging


class CommandFormatter(Formatter):
    """Format strings based on command patterns and configuration entries.

    Formatting follows these rules:

        - a ``True`` value is replaced with the key name of the field and
          prefixed with double dashes (--), also underscores are replaced with dashes

        - a field of the form ``{-o OPTION}`` is formatted according to the
          value of the 'OPTION' key then the flag '-o' and a space is added before that value

        - string values are added as is while list/tuple values are joined with a space

        - if bool(value) is False then the parameter is not added to the
          formatted command
    """

    def __init__(self, config):
        """Create a command formatter.

        Parameters
        ----------
        config: dict
            the configuration that the formatting is based on
        """
        self.config = config

    @lru_cache()
    def __call__(self, template):
        # don't polute self.config
        config = {}
        for key, val in self.config.items():
            if isinstance(val, bool):
                config[key] = '--' + key.lower().replace('_', '-') if val else ''
            else:
                config[key] = val
        # remove whitespace between args caused by empty optional parameters
        return ' '.join(self.format(template, **config).split())

    def get_value(self, key, args, kwargs):
        prefix = ''
        if key.startswith('-'):
            prefix, key, *_ = key.split()

        val = super().get_value(key, args, kwargs)

        if not val and val != 0:
            val = ''
        elif isinstance(val, (str, int)):
            if prefix:
                val = '{} {}'.format(prefix, val)
        elif isinstance(val, Iterable):
            if prefix:
                val = ('{} {}'.format(prefix, v) for v in val)
            val = ' '.join(map(str, val))
        return val


class BaseCommand(abc.ABC):
    """Base class of all command runners.

    Subclassing this ABC provides the following features:

        - A command template format string defined at the class level
          is formatted and run by invoking a method with the name
          'run_' + template name, for example::

              .. code:: python

                  class MyCommand(BaseCommand):
                      greet = 'echo hello {name}'

                  mycmd = MyCommand({'name': 'world'})
                  mycmd.run_greet()

        - Template formatting uses the provided configuration on
          the constructor, in the above example the command
          will be formatted to ``echo hello world``
    """

    command = ''

    def __init__(self, config):
        self._config = config
        self.formatter = CommandFormatter(config)
        self.dry_run = False
        self._cache = {}

    def __call__(self, *args, **kwargs):
        """Run the procedure."""
        self.dry_run = kwargs.get('dry_run', False)
        if self.dont_run():
            return
        self.run(*args, **kwargs)

    def __getitem__(self, name):
        return self._config[name]

    def __getattr__(self, name):
        cached = self._cache.get(name)
        if cached:
            return cached
        if not name.startswith('run_'):
            raise AttributeError('{} has no attribute {}'.format(type(self), name))

        _, template = name.split('_', maxsplit=1)

        def templated():
            """Format and run a command template."""
            command = self.formatter(getattr(self, template))
            return self._run_cmd(command)

        # inspection/debugging
        templated.__name__ = name
        self._cache[name] = templated
        return templated

    def _run_cmd(self, cmd):
        command = shlex.split(cmd)
        logging.debug("Running '%s':", cmd)
        if self.dry_run:
            return ''

        proc = sp.Popen(command, stdout=sp.PIPE, stderr=sp.PIPE)
        out, error = proc.communicate()  # block
        if proc.returncode == 0:
            return out.decode().strip()

        error = error.decode().strip()
        if not self.handle_error(cmd, error):
            msg = '{}: {}'.format(cmd, error)
            logging.error('Unhandled error: ' + msg)
            raise sp.SubprocessError(msg)

    @abc.abstractmethod
    def run(self, *args, **kwargs):
        """Describe the procedure."""

    @abc.abstractmethod
    def dont_run(self):
        """Return True to cancel running.
        This is called before run."""

    @abc.abstractmethod
    def handle_error(self, cmd, error):
        """Called on any error from commands. Return True
        to continue running or False to abort.
        """
