Installation
============

Install QTPyLib using ``pip``
------------------------------

.. code:: bash

    $ pip install qtpylib --upgrade --no-cache-dir


.. note::
    QTPyLib requires `IbPy <https://github.com/blampe/IbPy>`_, which, for some reason,
    cannot be bundled with the pip installer and requires manual installation.
    **To install IbPy manually, run:**

    .. code:: bash

        $ pip install git+git://github.com/blampe/IbPy --user --upgrade

Uninstall QTPyLib
~~~~~~~~~~~~~~~~~~

To uninstall QTPyLib using ``pip``, simply use:

.. code:: bash

    $ pip uninstall qtpylib


Possible Conda/Anaconda Issue
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you're using Python under a Conda/Anaconda enviroment, it is possible you'll run
into the following error message during installation that's caused by a
`documented Anaconda bug <https://github.com/ContinuumIO/anaconda-issues/issues/542>`_:

.. code:: bash

    Installing collected packages: setuptools, cryptography
        Found existing installation: setuptools 27.2.0
    Cannot remove entries from nonexistent file ~/anaconda3/lib/python/site-packages/easy-install.pth


To get ``conda`` to play nice with ``pip``, run this command before installing/upgrading QTPyLib:

.. code:: bash

    $ pip install --ignore-installed --upgrade pip setuptools



Requirements
~~~~~~~~~~~~

* `Python <https://www.python.org>`__ >=3.4
* `Pandas <https://github.com/pydata/pandas>`__ (tested to work with >=0.18.1)
* `Numpy <https://github.com/numpy/numpy>`__ (tested to work with >=1.11.1)
* `ØMQ <https://github.com/zeromq/pyzmq>`__ (tested to with with >=15.2.1)
* `PyMySQL <https://github.com/PyMySQL/PyMySQL>`__ (tested to with with >=0.7.6)
* `pytz <http://pytz.sourceforge.net>`__ (tested to with with >=2016.6.1)
* `dateutil <https://pypi.python.org/pypi/python-dateutil>`__ (tested to with with >=2.5.1)
* `Nexmo <https://github.com/Nexmo/nexmo-python>`__ for SMS support (tested to with with >=1.2.0)
* `Twilio <https://github.com/twilio/twilio-python>`__ for SMS support (tested to with with >=5.4.0)
* `Flask <http://flask.pocoo.org>`__ for the Dashboard (tested to work with >=0.11)
* `Requests <https://github.com/kennethreitz/requests>`__ (tested to with with >=2.10.0)
* `Beautiful Soup <https://pypi.python.org/pypi/beautifulsoup4>`_ (tested to work with >=4.3.2)
* `IbPy <https://github.com/blampe/IbPy>`__ (tested to work with >=0.7.2-9.00)
* `ezIBpy <https://github.com/ranaroussi/ezibpy>`__ (IbPy wrapper, tested to with with >=1.12.24)
* Latest Interactive Brokers’ `TWS <https://www.interactivebrokers.com/en/index.php?f=15875>`_ or `IB Gateway <https://www.interactivebrokers.com/en/index.php?f=16457>`_ installed and running on the machine

-----

Install IB TWS / Gateway
------------------------

In order for QTPyLib to be able to subscribe to market data and submit orders,
you must have the latest version of Interactive Brokers’
`TWS <https://www.interactivebrokers.com/en/index.php?f=15875>`_ or
`IB Gateway <https://www.interactivebrokers.com/en/index.php?f=16457>`_
installed, running and **properly configured** on your machine.


Installation
~~~~~~~~~~~~

Download TWS (offline version) or IB Gateway (requires less resources = recommended)
from Interactive Brokers’ website, and follow the installation instructions.

* `Download TWS (Traders Workstation) <https://www.interactivebrokers.com/en/index.php?f=15875>`_
* `Download IB Gateway <https://www.interactivebrokers.com/en/index.php?f=16457>`_


Configure for API Access
~~~~~~~~~~~~~~~~~~~~~~~~

After you install either TWS or IBGW, login using your account
(or use ``edemo``/``demouser``). The next thing to do is to go to the menu,
choose File, then choose **Global Configuration**.

Next, choose API on the left hand side, then go to **Settings**.

In the settings screen, make sure to set the options highlighted in the screenshot below:

.. image:: _static/tws1.jpg
    :width: 600px
    :alt: API Access

Next, go to **Precautions** on the left side menu, and make sure
***Bypass Order Precautions for API Orders** is checked.

.. image:: _static/tws2.jpg
    :width: 600px
    :alt: Order Confirmation

-----

Now that your system is setup, it's time to start programming your Algo...