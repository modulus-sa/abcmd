"""Helper functions for building command wrappers."""

import argparse
import sys

import logging
from logging import StreamHandler
from logging.handlers import SysLogHandler


def log_error_and_exit(err):
    """Log an Exception or a string on the Error loglevel and
    exit with non-zero status code."""
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
