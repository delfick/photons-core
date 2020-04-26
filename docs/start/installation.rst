.. installation:

Requirements
============

Photons requires a UNIX-like operating system (Linux, macOS, Windows Subsystem
for Linux) with Python 3.6 or newer installed.

Installation
============

Photons is best installed in a Python virtual environment. The following commands
create a virtual environment in the ``~/.photons-core`` directory and
installs the latest version of Photons::

    $ python3 -m venv ~/.photons-core
    $ source ~/.photons-core/bin/activate
    $ pip install lifx-photons-core

After installation, the Photons command-line tool ``lifx`` is available in the virtual
environment::

    $ lifx lan:transform -- '{"power": "on", "color": "red", "brightness": 0.5}'

.. _activation:

Activating the virtual environment
------------------------------------

The installation method above installs Photons into a virtual environment which
needs to be activated prior to use. The activation command can be included in larger
shell scripts to make the ``lifx`` utility available to those scripts.

To activate the virtual environment, run::

    $ source ~/.photons-core/bin/activate

To deactivate the virtual environment, run::

    (.photons-core) $ deactivate
