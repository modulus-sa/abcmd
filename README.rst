abcmd
=====

.. image:: https://img.shields.io/pypi/v/abcmd.svg
    :target: https://pypi.python.org/pypi/abcmd
    :alt: Latest PyPI version

.. image:: https://travis-ci.org/modulus-sa/abcmd.svg?branch=master
    :target: https://travis-ci.org/modulus-sa/abcmd

.. image:: https://codecov.io/gh/modulus-sa/abcmd/branch/master/graph/badge.svg
  :target: https://codecov.io/gh/modulus-sa/abcmd

A library for wrapping shell commands with static configuration.

Usage
-----

The library provides the ``abcmd.Command`` ABC and two mixins
``abcmd.config.Checker`` and ``abcmd.config.Loader`` that can be used
to create shell command wrappers.


Examples
--------

Automating backup of dotfiles:

.. code-block:: python

    import datetime
    import abcmd

    class Backup(abcmd.Command):
        make = 'mkdir ~/{directory}'
        copy = 'cp {files} ~/{directory}'
        sync = 'rsync {directory} {user}@{server}:~/{directory} '

        def run(self, *args, **kwargs):
            run_make()
            run_copy()
            run_sync()

        def dont_run(self, *args, **kwargs):
            # don't run between working hours
            return dt.datetime.now().hour in range(8, 16)

        def handle_error(self, cmd, error):
            # if the backup directory exists ignore the error and continue
            return cmd.startswith('mkdir') and error.endswith('File exists')

    config = {
        'user': 'laerus',
        'directory': 'dotfiles',
        'files': ['~/.vimrc', '~/.bashrc', '~/.inputrc'],
        'server': '192.168.1.10'
    }

    runner = Backup(config)
    runner()


This will run the following commands:

.. code-block:: shell

    $ mkdir ~/dotfiles 
    $ cp ~/.vimrc ~/.bashrc ~/.inputrc ~/dotifles
    $ rsync dotfiles laerus@192.168.1.10:~/dotfiles


Installation
------------

.. code-block:: shell

    $ pip install abcmd

Compatibility
-------------
python3.5+

Licence
-------
MIT

Authors
-------

`abcmd` was written by `Konstantinos Tsakiltzidis <https://github.com/laerus>`_.
