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

The library provides the ``abcmd.Command`` ABC that can be used
to create shell command wrappers.

Examples
--------

Automating backup of dotfiles

First we subclass ``Command`` and describe the procedure:

.. code-block:: python

    import datetime
    import os

    import abcmd

    class Backup(abcmd.Command):
        make = 'mkdir {directory}'
        copy = 'cp {files} {directory}'
        sync = 'rsync {directory} {user}@{server}:'

        def run(self, *args, **kwargs):
            os.chdir(os.environ['HOME'])
            self.run_make()
            self.run_copy()
            self.run_sync()

        def dont_run(self, *args, **kwargs):
            # don't run between working hours
            return dt.datetime.now().hour in range(8, 16)

        def handle_error(self, cmd, error):
            # if the backup directory exists ignore the error and continue
            return cmd.startswith('mkdir') and error.endswith('File exists')

then we instantiate with a mapping that is used to render the templates,
this will return a callable object that when called will run the procedure:

.. code-block:: python

    config = {
        'user': 'laerus',
        'directory': 'dotfiles',
        'files': ['.vimrc', '.bashrc', '.inputrc'],
        'server': '192.168.1.10'
    }

    runner = Backup(config)
    runner()


This would be equivalent with running the following commands:

.. code-block:: shell

    $ cd ~
    $ mkdir dotfiles 
    $ cp .vimrc .bashrc .inputrc dotfiles
    $ rsync dotfiles laerus@192.168.1.10:


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
