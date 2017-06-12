"""Prototype classes for Backup command (borg, rsync)"""

import abc
import datetime as dt
import logging
import shlex
import subprocess as sp
import smtplib

from abcmd import BaseCommand
from abcmd.config import Checker, Loader
from abcmd.utils import log_error_and_exit


class BackupConfig(Checker, Loader):
    """Prototype configuration for borg/rsync"""
    allowed_hours = list
    email_from = str
    email_to = str
    exclude = []
    minimum_interval = int
    paths = list
    verbose = False
    pre_scripts = list
    post_scripts = list
    disabled = False
    LALALA = 10


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
