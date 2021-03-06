"""abcmd - ABCs & Mixins for wrapping commands with static configuration."""

__version__ = "0.4.0"
__author__ = "Konstantinos Tsakiltzidis <ktsakiltzidis@modulus.gr>"
__all__ = ("Command",)


import abc
import re
import shlex
import subprocess as sp
import sys
from functools import lru_cache
from string import Formatter
import logging

if sys.version_info.minor < 5:
    import collections as cabc
    from .typingstub import Any, Union, Sequence, Mapping, Callable
else:
    import collections.abc as cabc
    from typing import Any, Union, Sequence, Mapping, Callable

if sys.version_info.minor < 3:

    class SubprocessError(Exception):
        """Called when a process errors for python < 3.4"""

    sp.SubprocessError = SubprocessError


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

    def __init__(self, config: Mapping[str, Any]) -> None:
        """Create a command formatter.

        Parameters
        ----------
        config: dict
            the configuration that the formatting is based on
        """
        self._config = config

    @property
    def config(self):
        self.__call__.cache_clear()
        return self._config

    @lru_cache()
    def __call__(self, template: str) -> str:
        # don't polute self._config
        config = {}
        for key, val in self._config.items():
            if isinstance(val, bool):
                config[key] = "--" + key.lower().replace("_", "-") if val else ""
            else:
                config[key] = val
        # remove whitespace between args caused by empty optional parameters
        return " ".join(self.format(template, **config).split())

    def get_value(
        self, key: Union[str, int], args: Sequence[Any], kwargs: Mapping[str, Any]
    ) -> Any:
        if not isinstance(key, str):
            return ""
        flag = ""
        if key.startswith("-"):
            flag, key, *_ = key.split()

        val = super().get_value(key, args, kwargs)

        if not val and val != 0:
            val = ""
        elif isinstance(val, (str, int)):
            if flag:
                val = "{} {}".format(flag, val)
        elif isinstance(val, cabc.Iterable):
            if flag:
                val = ("{} {}".format(flag, v) for v in val)
            val = " ".join(map(str, val))
        else:
            val = str(val)
        return val


class CommandDescriptor:
    def __init__(self, name, template):
        self.name = name
        self.template = template
        self.runners = {}

    def __get__(self, command, cls):
        if not command:
            return self
        if command in self.runners:
            return self.runners[command]

        runner = Process(self.name, command, self.template)
        self.runners[command] = runner
        return runner


class Process:
    def __init__(self, name, command, template):
        self.name = name
        self.command = command
        self.template = template

    def __call__(self, *args, **kwargs):
        self.returncode, self.output, self.error = self.command._runner(str(self))
        if self.returncode != 0:
            self.handle_error()
        return self

    def __str__(self):
        self._formatted_command = self.command._formatter(self.template)
        return self._formatted_command

    def handle_error(self):
        handlers = self.get_error_handlers()

        if handlers:
            for handler in handlers:
                if not handler(self.command, self.error):
                    break
            else:
                return
        elif hasattr(self.command, "handle_error"):
            if self.command.handle_error(self._formatted_command, self.error):
                return

        msg = "{}: {}".format(self._formatted_command, self.error)
        logging.error("Unhandled error: " + msg)
        raise sp.SubprocessError(msg)

    def get_error_handlers(self):
        return [
            handler
            for handler in self.command._handlers
            if self.is_matching_handler(handler)
        ]

    def is_matching_handler(self, handler):
        command_name = handler._handler["command"]
        if command_name and self.name != command_name:
            return False
        error_pattern = handler._handler["error"]
        if error_pattern and not re.search(error_pattern, self.error):
            return False
        rc_pattern = handler._handler["rc"]
        if rc_pattern and rc_pattern != self.returncode:
            return False
        return True

    def __repr__(self):
        return "{} runner at {}".format(self.name, id(self))


class MetaCommand(abc.ABCMeta):
    def __new__(cls, name, bases, namespace):
        if not bases:
            return super().__new__(cls, name, bases, namespace)

        # gather from parent classes as well
        error_handlers = [
            handler for base in bases for handler in getattr(base, "_handlers", ())
        ]

        for key, val in namespace.items():
            if key.startswith("_"):
                continue
            elif isinstance(val, str):
                namespace[key] = CommandDescriptor(key, val)
            elif callable(val) and hasattr(val, "_handler"):
                error_handlers.append(val)

        namespace["_handlers"] = error_handlers

        return super().__new__(cls, name, bases, namespace)


class Command(metaclass=MetaCommand):
    """Base class of all command runners.

    Subclassing provides the following features:

        - A string defined at the class level is formatted and run by calling
          the attribute, for example::

              .. code:: python

                  class MyCommand(Command):
                      greet = 'echo hello {name}'

                  mycmd = MyCommand({'name': 'world'})
                  mycmd.greet()

          Formatting uses the provided configuration
          on initiation, in the above example the command
          will be formatted to ``echo hello world``

      - The following methods are optional and implementing them will
        provider additional functionality

            - ``self.dont_run`` will be called before ``self.run`` and if
              the returning value is truthy it will cancel the procedure

            - ``self.before_run`` and ``self.after_run`` are called
              before and after the ``self.run`` method respectively

            - ``self.handle_error`` will be called on any errors that
              have not been handled by methods decorated by the
              ``error_handler`` decorator, return a falsy value will make
              the procedure stop

      - Decorating a method with the ``error_handler`` decorator
        will call that method on any matching errors, returing a
        falsy value will make the procedure stop


    """

    def __init__(self, config: Mapping, *, runner: Callable = None) -> None:
        self._config = config
        self._runner = runner if runner is not None else _run_cmd
        self._formatter = CommandFormatter(self._config)

    def __call__(self, *args: Any, **kwargs: Any) -> None:
        """Run the procedure."""
        if hasattr(self, "dont_run") and self.dont_run():
            return

        if hasattr(self, "before_run"):
            self.before_run()

        self.run(*args, **kwargs)

        if hasattr(self, "after_run"):
            self.after_run()

    @property
    def config(self):
        self._formatter.__call__.cache_clear()
        return self._config

    @abc.abstractmethod
    def run(self, *args: Any, **kwargs: Any) -> None:
        """Describe the procedure."""


def _run_cmd(cmd: str) -> str:
    command = shlex.split(cmd)
    logging.debug("Running '%s':", cmd)

    proc = sp.Popen(command, stdout=sp.PIPE, stderr=sp.PIPE)
    out, error = proc.communicate()  # block
    try:
        out = out.decode()
        error = error.decode()
    except UnicodeDecodeError:
        msg = (
            "Unicode error while decoding command output, "
            "replacing offending characters."
        )
        logging.warning(msg)
        out = out.decode(errors="replace")
        error = error.decode(errors="replace")

    return (proc.returncode, out, error)


def error_handler(command=None, error=None, rc=None):
    """Method decorator for handling specific errors.
    First argument is command to match too, the second argument
    is a regular expression to match the error."""

    def wrapper(func):
        func._handler = {"command": command, "error": error, "rc": rc}
        return func

    return wrapper
