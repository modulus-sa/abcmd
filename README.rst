abcmd
=====

.. image:: https://img.shields.io/pypi/v/abcmd.svg
    :target: https://pypi.python.org/pypi/abcmd
    :alt: Latest PyPI version

.. image:: https://travis-ci.org/modulus-sa/abcmd.svg?branch=master
    :target: https://travis-ci.org/modulus-sa/abcmd

A library for wrapping shell commands with static configuration.

Usage
-----

The library provides the ``abcmd.BaseCommand`` ABC and two mixins
``abcmd.config.Checker`` and ``abcmd.config.Loader`` that can be used
to create shell command wrappers.

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
