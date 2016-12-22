QTPyLib, Pythonic Algorithmic Trading
=====================================

.. image:: https://img.shields.io/pypi/pyversions/qtpylib.svg?maxAge=2592000
    :target: https://pypi.python.org/pypi/qtpylib
    :alt: Python version

.. image:: https://img.shields.io/travis/ranaroussi/qtpylib/master.svg?
    :target: https://travis-ci.org/ranaroussi/qtpylib
    :alt: Travis-CI build status

.. image:: https://img.shields.io/pypi/v/qtpylib.svg?maxAge=60
    :target: https://pypi.python.org/pypi/qtpylib
    :alt: PyPi version

.. image:: https://img.shields.io/pypi/status/qtpylib.svg?maxAge=2592000
    :target: https://pypi.python.org/pypi/qtpylib
    :alt: PyPi status

.. image:: https://img.shields.io/badge/docs-latest-brightgreen.svg?style=flat
    :target: http://qtpylib.io/docs/latest/?badge=latest
    :alt: Documentation Status

.. image:: https://img.shields.io/github/stars/ranaroussi/qtpylib.svg?style=social&label=Star&maxAge=60
    :target: https://github.com/ranaroussi/qtpylib
    :alt: Star this repo

.. image:: https://img.shields.io/twitter/follow/aroussi.svg?style=social&label=Follow%20Me&maxAge=60
    :target: https://twitter.com/aroussi
    :alt: Follow me on twitter

\

QTPyLib (**Q**\ uantitative **T**\ rading **Py**\ thon **Lib**\ rary)
is a simple, event-driven algorithmic trading system written in Python 3,
that supports backtesting and live trading using
`Interactive Brokers <https://www.interactivebrokers.com>`_
for market data and order execution.

I originally developed QTPyLib because I wanted for a simple
(but powerful) trading library that will let me to focus on the
trading logic itself and ignore everything else.

`Full Documentation » <http://www.qtpylib.io/>`_

`Changelog » <./CHANGELOG.rst>`_

-----

Features
========

- A continuously-running Blotter that lets you capture market data even when your algos aren't running.
- Tick, Bar and Trade data is stored in MySQL for later analisys and backtesting.
- Using pub/sub architecture using `ØMQ <http://zeromq.org>`_ (ZeroMQ) for communicating between the Algo and the Blotter allows for a single Blotter/multiple Algos running on the same machine.
- **Support for Order Book, Quote, Time, Tick or Volume based strategy resolutions**.
- Includes many common indicators that you can seamlessly use in your algorithm.
- **Market data events uses asynchronous, non-blocking architecture**.
- Have orders delivered to your mobile via SMS (requires a `Nexmo <https://www.nexmo.com/>`_ or `Twilio <https://www.twilio.com/>`_ account).
- Full integration with `TA-Lib <http://ta-lib.org>`_ via dedicated module (`see documentation <http://qtpylib.io/docs/latest/indicators.html#ta-lib-integration>`_).
- Ability to import any Python library (such as `scikit-learn <http://scikit-learn.org>`_ or `TensorFlow <https://www.tensorflow.org>`_) to use them in your algorithms.

-----

Quickstart
==========

There are 5 main components to QTPyLib:

1. ``Blotter`` - handles market data retreival and processing.
2. ``Broker`` - sends and proccess orders/positions (abstracted layer).
3. ``Algo`` - (sub-class of ``Broker``) communicates with the ``Blotter`` to pass market data to your strategies, and proccess/positions orders via ``Broker``.
4. ``Reports`` - provides real time monitoring of trades and open opsitions via Web App, as well as a simple REST API for trades, open positions and market data.
5. Lastly, **Your Strategies**, which are sub-classes of ``Algo``, handle the trading logic/rules. This is where you'll write most of your code.


1. Get Market Data
------------------

To get started, you need to first create a Blotter script:

.. code:: python

    # blotter.py
    from qtpylib.blotter import Blotter

    class MainBlotter(Blotter):
        pass # we just need the name

    if __name__ == "__main__":
        blotter = MainBlotter()
        blotter.run()

Then, with IB TWS/GW running, run the Blotter from the command line:

.. code:: bash

    $ python blotter.py

If your strategy needs order book / market depth data, add the ``--orderbook`` flag to the command:

.. code:: bash

    $ python blotter.py --orderbook


2. Write your Algorithm
-----------------------

While the Blotter running in the background, write and execute your algorithm:

.. code:: python

    # strategy.py
    from qtpylib.algo import Algo

    class CrossOver(Algo):

        def on_start(self):
            pass

        def on_fill(self, instrument, order):
            pass

        def on_quote(self, instrument):
            pass

        def on_orderbook(self, instrument):
            pass

        def on_tick(self, instrument):
            pass

        def on_bar(self, instrument):
            # get instrument history
            bars = instrument.get_bars(window=100)

            # or get all instruments history
            # bars = self.bars[-20:]

            # skip first 20 days to get full windows
            if len(bars) < 20:
                return

            # compute averages using internal rolling_mean
            bars['short_ma'] = bars['close'].rolling_mean(window=10)
            bars['long_ma']  = bars['close'].rolling_mean(window=20)

            # get current position data
            positions = instrument.get_positions()

            # trading logic - entry signal
            if bars['short_ma'].crossed_above(bars['long_ma'])[-1]:
                if not instrument.pending_orders and positions["position"] == 0:

                    # buy one contract
                    instrument.buy(1)

                    # record values for later analysis
                    self.record(ma_cross=1)

            # trading logic - exit signal
            elif bars['short_ma'].crossed_below(bars['long_ma'])[-1]:
                if positions["position"] != 0:

                    # exit / flatten position
                    instrument.exit()

                    # record values for later analysis
                    self.record(ma_cross=-1)


    if __name__ == "__main__":
        strategy = CrossOver(
            instruments = [ ("ES", "FUT", "GLOBEX", "USD", 201609, 0.0, "") ], # ib tuples
            resolution  = "1T", # Pandas resolution (use "K" for tick bars)
            tick_window = 20, # no. of ticks to keep
            bar_window  = 5, # no. of bars to keep
            preload     = "1D", # preload 1 day history when starting
            timezone    = "US/Central" # convert all ticks/bars to this timezone
        )
        strategy.run()


To run your algo in a **live** enviroment, from the command line, type:

.. code:: bash

    $ python strategy.py --logpath ~/qtpy/


The resulting trades be saved in ``~/qtpy/STRATEGY_YYYYMMDD.csv`` for later analysis.


3. Viewing Live Trades
----------------------

While the Blotter running in the background, write the dashboard:

.. code:: python

    # dashboard.py
    from qtpylib.reports import Reports

    class Dahboard(Reports):
        pass # we just need the name

    if __name__ == "__main__":
        dashboard = Dahboard(port = 5000)
        dashboard.run()


To run your dashboard, run it from the command line:

.. code:: bash

    $ python dashboard.py

    >>> Dashboard password is: a0f36d95a9
    >>> Running on http://0.0.0.0:5000/ (Press CTRL+C to quit)

Now, point your browser to http://localhost:5000 and use the password generated to access your dashboard.

-----

.. note::
    Please refer to the `Full Documentation <http://www.qtpylib.io/>`_ to learn
    how to enable SMS notifications, use the bundled Indicators, and more.



Installation
============

Install using ``pip``:

.. code:: bash

    $ pip install qtpylib --upgrade --no-cache-dir


Requirements
------------

* `Python <https://www.python.org>`_ >=3.4
* `Pandas <https://github.com/pydata/pandas>`_ (tested to work with >=0.18.1)
* `Numpy <https://github.com/numpy/numpy>`_ (tested to work with >=1.11.1)
* `PyZMQ <https://github.com/zeromq/pyzmq>`_ (tested to with with >=15.2.1)
* `PyMySQL <https://github.com/PyMySQL/PyMySQL>`_ (tested to with with >=0.7.6)
* `pytz <http://pytz.sourceforge.net>`_ (tested to with with >=2016.6.1)
* `dateutil <https://pypi.python.org/pypi/python-dateutil>`_ (tested to with with >=2.5.1)
* `Nexmo-Python <https://github.com/Nexmo/nexmo-python>`_ for SMS support (tested to with with >=1.2.0)
* `Twilio-Python <https://github.com/twilio/twilio-python>`_ for SMS support (tested to with with >=5.4.0)
* `Flask <http://flask.pocoo.org>`_ for the Dashboard (tested to work with >=0.11)
* `Requests <https://github.com/kennethreitz/requests>`_ (tested to with with >=2.10.0)
* `Beautiful Soup <https://pypi.python.org/pypi/beautifulsoup4>`_ (tested to work with >=4.3.2)
* `IbPy2 <https://github.com/blampe/IbPy>`_ (tested to work with >=0.8.0)
* `ezIBpy <https://github.com/ranaroussi/ezibpy>`_ (IbPy wrapper, tested to with with >=1.12.44)
* Latest Interactive Brokers’ `TWS <https://www.interactivebrokers.com/en/index.php?f=15875>`_ or `IB Gateway <https://www.interactivebrokers.com/en/index.php?f=16457>`_ installed and running on the machine
* `MySQL Server <https://www.mysql.com/>`_ installed and running with a database for QTPyLib

-----

Legal Stuff
===========

QTPyLib is distributed under the **GNU Lesser General Public License v3.0**. See the `LICENSE.txt <./LICENSE.txt>`_ file in the release for details.
QTPyLib is not a product of Interactive Brokers, nor is it affiliated with Interactive Brokers.


You can find other examples in the qtpylib/examples directory.

P.S.
----

I'm very interested in your experience with QTPyLib. Please drop me an note with any feedback you have.

**Ran Aroussi**