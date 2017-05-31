"""Abstract Classes to create cli command wrappers that are configured
statically with a file."""

import abc
import argparse
import datetime as dt
import os
import pprint
import shlex
import smtplib
import subprocess as sp
import sys
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from string import Formatter
import logging
from logging import StreamHandler
from logging.handlers import SysLogHandler


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


# Backup Prototypes

class BackupConfig(BaseConfig):
    """Prototype configuration for borg/rsync"""
    allowed_hours = list
    disabled = False
    email_from = str
    email_to = str
    exclude = []
    minimum_interval = int
    paths = list
    verbose = False
    pre_scripts = list
    post_scripts = list


class Backup(BaseCommand):
    """Prototype for borg/rsync."""

    def __call__(self, *args, **kwargs):
        """Run the procedure."""
        if self.dont_run():
            return

        self.dry_run = kwargs.get('dry_run', False)

        logging.info('Running pre-backup scripts...')
        self.run_scripts(self['pre_scripts'])

        self.run(*args, **kwargs)

        logging.info('Running post-backup scripts...')
        self.run_scripts(self['post_scripts'])

    @abc.abstractmethod
    def get_last_backup_time(self):
        """Get the timestamp of the last backup."""

    def dont_run(self):
        if self['disabled']:
            logging.info('{} task is disabled...'.format(self.__class__.__name__))
            return True
        if self.is_bad_time():
            logging.info('Not yet time to backup...')
            return True
        if self.has_recent_backup():
            logging.info('There was a recent backup, aborting...')
            return True
        return False

    def has_recent_backup(self):
        """Check if there was a previous backup within ``minimum_interval``."""
        last_ts = self.get_last_backup_time()
        if not last_ts:
            return False
        minimum_interval = self['minimum_interval']
        return dt.datetime.now() - last_ts < dt.timedelta(seconds=minimum_interval)

    def is_bad_time(self):
        """Check whether the current hour is in ``allowed hours``."""
        return dt.datetime.now().hour not in self['allowed_hours']

    def run_scripts(self, scripts):
        "Execute a list of commands."
        assert all(map(lambda cmd: isinstance(cmd, str), scripts))
        for cmd in scripts:
            logging.debug('Executing: %s', cmd)
            if self.dry_run:
                continue
            try:
                out = sp.check_output(shlex.split(cmd))
                logging.debug('Output: %s', out)
            except sp.SubprocessError as err:
                log_error_and_exit(err)

    def send_mail(self, subject):
        """Send mail to predefined host."""
        server = smtplib.SMTP('localhost')
        e_from = self['email_from']
        e_to = self['email_to']
        msg = ('From: {email_from}\r\nTo: {email_to}\r\n\r\n{subject}'
               '').format(email_from=e_from, email_to=e_to, subject=subject)
        try:
            server.sendmail(e_from, e_to, msg)
        except Exception as err:
            logging.warning('Could not send email: {}'.format(err))


def log_error_and_exit(err):
    """Log an Exception or a string on the Error loglevel and
    exit with non-zero status code."""
    print("LOGGING:", logging, type(logging))
    logging.error(err)
    sys.exit(2)


def parse_args(args=None, confdir=None):
    if args is None:
        args = sys.argv[1:]
    parser = argparse.ArgumentParser()
    parser.add_argument('task', type=str, metavar='TASK', help='name of the task')
    parser.add_argument('-c', '--configpath', default=confdir,
                        metavar='PATH', help='the configuration path')
    parser.add_argument('--dry-run', action='store_true', help='check without doing any changes.')
    return parser.parse_args(args)


def setup_logging(proc, task):
    """Set logging include proc and task name in the logging message."""
    logging.basicConfig(format=('{proc}[{{process}}] {task}: {{levelname}}: {{message}}'
                                '').format(proc=proc, task=task),
                        style='{', level=logging.DEBUG,
                        handlers=[StreamHandler(stream=sys.stdout),
                                  SysLogHandler('/dev/log')])


def build_wrapper(task, configpath, cmd_cls, config_cls):
    """Build a command wrapper based on custom defined classes."""
    loader = config_cls()
    try:
        config = loader(task, configpath)
    except (MissingConfigurationError, UnknownFormatError, FileNotFoundError) as err:
        log_error_and_exit(err)

    return cmd_cls(config)
