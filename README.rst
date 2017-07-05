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


Using the ``config.Loader`` mixin makes it possible to retrieve
the static configuration from a file:

Changing the ``Backup`` class above to inherit from ``config.Loader``

.. code-block:: python

    class Backup(abcmd.Command, abcmd.config.Loader):
        ...

and creating a file with the configuration:

.. code-block:: yaml

    # dotfiles-backup.yaml

    user: laerus
    directory: dotfiles
    files:
      - .vimrc
      - .bashrc
      - .inputrc
    server: 192.168.1.10

We can then just run:

.. code-block:: python

    runner = Backup('dotfiles-backup')
    runner()

assuming the file is in the current working directory.  Notice how we didn't specify
the extension of the file, that is because the ``Loader`` class automatically searches
for known file extensions and uses the appropriate module to load the configuration,
at the moment the supported formats are ``json``, ``yaml`` and ``toml``.

The ``config.Checker`` mixin provides a convenient way of checking the configuration
at instantiation, we first create a subclass that describes the required configuration
entries and their type at the class level:

.. code-block:: python

    class BackupConfig(abcmd.config.Checker):
        user = str
        directory = 'dotfiles'
        files = list
        server = str

    class Backup(abcmd.Command, BackupConfig):
        ...

assining a configuration entry to an object than a type would make use of this value
as the default value in case the entry is missing:

.. code-block:: python
    
    config = {
        'user': 'laerus',
        'files': ['.vimrc', '.bashrc', '.inputrc'],
        'server': '192.168.1.10'
    }

    runner = Backup(config)
    runner()

this will check each configuration entry against the types specified as
the ``BackupConfig`` class attributes and will also add the missing
``directory`` entry with the value ``'dotfiles'``

If there is a type mismatch a ``TypeError`` is raised at the instantiation
of ``Backup``, for example if the above configuration was:

.. code-block:: python

    config = {
        'user': 10  # not a string
        'files': ['.vimrc', '.bashrc', '.inputrc'],
        'server': '192.168.1.10'
    }

running:

.. code-block:: python

    runner = Backup(config)

will result in a ``TypeError: 'user' must be of type 'int' not 'str'`` being raised.
If a configuration entry is missing and there is not a provided default it will raise
a ``config.MissingConfigurationEntry`` instead.


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
