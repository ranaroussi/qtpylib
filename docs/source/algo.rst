Writing Your Algorithm
======================

When creating your algorithm, there are 4 functions that handle
incoming market data from the running Blotter. These are
``on_quote()`` which is invoked on every quote change,
``on_tick()`` which is invoked on every tick captured,
``on_bar()``, which is invoked on every bar created in the pre-specified resolution, and
``on_orderbook()``, which is invoked on every change to the Order Book.

An `Instrument Object <./api_instrument.html>`_ is being passed to each method when called.

If you need to run some logic when your strategy starts,
simply add an ``on_start()`` method to your strategy, and set
your parameters there.

If your strategy requires you to take action on every fill,
simply add an ``on_fill()`` method to your strategy, and
run write code logic there.

All methods are optional. You can run logic on start *and/or*
on every tick *and/or* on every bar event as needed. Unnecessary can
either use ``pass`` or be omitted from your strategy code.


.. warning::
    You're going to lose a lot of money very quickly by
    running the sample algorithms in this documentation!
    **Please use the demo account when logging into
    IB TWS / IB Gateway (user: edemo, password: demouser).**


Basic Algo Structure
--------------------

Here's a code for an algo that buys Apple Stock when flat
and sells when in position.

.. code:: python

    # strategy.py
    from qtpylib.algo import Algo

    class DumbAlgo(Algo):

        def on_start(self):
            # optional method that gets called once upon start
            pass

        def on_fill(self, instrument, order):
            # optional method that gets called on every order fill
            pass

        def on_orderbook(self, instrument):
            # optional method that gets called on every orderbook change
            pass

        def on_quote(self, instrument):
            # optional method that gets called on every quote change
            pass

        def on_tick(self, instrument):
            # optional method that gets called on every tick received
            pass

        def on_bar(self, instrument):
            # optional method that gets called on every bar received

            # buy if position = 0, sell if in position > 0
            if instrument.positions['position'] == 0:
                instrument.buy(100)
            else:
                instrument.exit()


    if __name__ == "__main__":

        # initialize the algo
        strategy = DumbAlgo(
            instruments = [ "AAPL" ],
            resolution  = "1T" # 1Min bar resolution (Pandas "resample" resolutions)
        )

        # run the algo
        strategy.run()


With your Blotter running in the background, run your algo from the command line:

.. code:: bash

    $ python strategy.py


The algo will communicate with the Blotter running in the background and
generate orders based on the rules specified.

.. note::
    A trade log will be saved in the database specified in the
    currently running Blotter and will be available via the
    :doc:`reports`.


-----


Simple MA Cross Over Strategy
-----------------------------

While the Blotter running in the background, write and execute your algorithm:

.. code:: python

    # strategy.py
    from qtpylib.algo import Algo

    class CrossOver(Algo):

        def on_bar(self, instrument):

            # get instrument history
            bars = instrument.get_bars(window=20)

            # make sure we have at least 20 bars to work with
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

                    # send a buy signal
                    instrument.buy(1)

                    # record values for future analysis
                    self.record(ma_cross=1)

            # trading logic - exit signal
            elif bars['short_ma'].crossed_below(bars['long_ma'])[-1]:
                if positions["position"] != 0:

                    # exit / flatten position
                    instrument.exit()

                    # record values for future analysis
                    self.record(ma_cross=-1)


    if __name__ == "__main__":
        strategy = CrossOver(
            instruments = [ ("CL", "FUT", "NYMEX", "USD", 201609) ],
            resolution  = "1H"
        )

        strategy.run()


With your Blotter running in the background, run your algo from the command line:

.. code:: bash

    $ python strategy.py --log ~/qtpylib/


By adding ``--log ~/qtpylib/`` we ask that the resulting trade journal be saved
in ``~/qtpylib/STRATEGY_YYYYMMDD.csv`` for later analysis **in addition** to
being saved in the database.

-----

Using Multiple Instruments
--------------------------

.. code:: python

    # strategy.py
    from qtpylib.algo import Algo

    class BuyStockSellOil(Algo):

        def on_bar(self, instrument):

            # get instrument object
            ES = self.get_instrument('ESU2016_FUT')
            CL = self.get_instrument('CLU2016_FUT')

            # rotate holding between ES and CL
            # yes - this strategy makes no sense :)

            es_pos = ES.get_positions()
            cl_pos = CL.get_positions()

            if es_pos["position"] == 0 and cl_pos["position"] > 0:
                ES.buy(1)
                CL.exit(1)
            elif es_pos["position"] > 0 and cl_pos["position"] == 0:
                ES.exit(1)
                CL.buy(1)


    if __name__ == "__main__":
        strategy = BuyStockSellOil(
            instruments = [
                ("ES", "FUT", "GLOBEX", "USD", 201609),
                ("CL", "FUT", "NYMEX", "USD", 201609)
            ],
            resolution  = "15T"
        )

        strategy.run()


-----

Initializing Parameters
-----------------------

Sometimes you'd want to set some parameters when you initialize
your Strategy. To do so, simply add an ``on_start()`` method
to your strategy, and set your parameters there. It will be
invoked once when you strategy starts.


.. code:: python

    # strategy.py
    from qtpylib.algo import Algo

    class MyStrategy(Algo):

        def on_start(self):
            self.paramA = "a"
            self.paramB = "b"

        ...

-----

Adding Contracts After Initialization
-------------------------------------

In some cases, you'd want to add instruments/contracts to your
Strategy after it has already been initialized.

This can be achieved using:

.. code:: python

    # strategy.py
    strategy = MyStrategy(
        instruments = ["AAPL"]
        resolution  = "1T"
    )

    strategy.add_instruments("GOOG", "MSFT", "FUT.ES", ...)
    # ^^ accepts strings, IB contracts and instrument Tuples

    strategy.run()


-----

Available Arguments
-------------------

Below are all the parameters that can either be set via the ``Algo()``
or via CLI (**all are optional**).

Algo Parameters
~~~~~~~~~~~~~~~

- ``instruments`` List of stock symbols (for US Stocks) / IB Contract Tuples. Default is empty (no instruments)
- ``resolution`` Bar resolution (pandas resample resolution + ``K`` for tick bars and ``V`` for volume bars). Default is 1T (1 min)
- ``tick_window`` Length of tick lookback window to keep (defaults to ``1``)
- ``bar_window`` Length of bar lookback window to keep (defaults to ``100``)
- ``timezone`` Convert IB timestamps to this timezone, eg. "US/Central" (defaults to ``UTC``)
- ``preload`` Preload history upon start (eg. 1H, 2D, etc, or K for tick bars). (defaults to ``None``)
- ``continuous`` Tells preloader to construct continuous Futures contracts (default is ``True``)
- ``blotter`` Log trades to MySQL server used by this Blotter (default: ``auto-detect``).
- ``backtest`` Work in Backtest mode (default: ``False``)
- ``start`` Backtest start date (``YYYY-MM-DD [HH:MM:SS[.MS]``)
- ``end`` Backtest end date (``YYYY-MM-DD [HH:MM:SS[.MS]``)
- ``data`` Path to the directory with `QTPyLib-compatible CSV files <./workflow.html>`_ (back-testing mode only)
- ``output`` Path to save the recorded data (default: ``None``)
- ``sms`` List of numbers to text orders (default: ``None``)
- ``log`` Path to store trade data (default: ``None``)
- ``ibport`` IB TWS/GW Port to use (default: ``4001``)
- ``ibclient`` IB TWS/GW Client ID (default: ``998``)
- ``ibserver`` IB TWS/GW Server hostname (default: ``localhost``)

**Example:**

.. code:: python

    # strategy.py
    ...

    strategy = MyStrategy(
        instruments = [ "AAPL" ],
        resolution  = "512K", # 512 tick bars
        tick_window = 10, # keep last 10 ticks bars
        bar_window  = 500,  # keep last 500 (tick) bars
        preload     = "4H", # pre-load the last 4 hours of tick bar data
        timezone    = "US/Central", # convert all tick/bar timestamps to "US/Central"
        blotter     = "MainBlotter" # use this blotter's database to store the trade log
    )
    strategy.run()


Runtime (CLI) Parameters
~~~~~~~~~~~~~~~~~~~~~~~~

You can override any of the above parameters using run-time using command line arguments:

- ``--ibport`` IB TWS/GW Port to use (default: ``4001``)
- ``--ibclient`` IB TWS/GW Client ID (default: ``998``)
- ``--ibserver`` IB TWS/GW Server hostname (default: ``localhost``)
- ``--sms`` List of numbers to text orders (default: ``None``)
- ``--log`` Path to store trade data (default: ``None``)
- ``--backtest`` Work in Backtest mode (flag, default: ``False``)
- ``--start`` Backtest start date (``YYYY-MM-DD [HH:MM:SS[.MS]``)
- ``--end`` Backtest end date (``YYYY-MM-DD [HH:MM:SS[.MS]``)
- ``--data`` Path to the directory with `QTPyLib-compatible CSV files <./workflow.html>`_ (back-testing mode only)
- ``--output`` Path to save the recorded data (default: ``None``)
- ``--blotter`` Log trades to MySQL server used by this Blotter (default: ``auto-detect``)
- ``--continuous`` Construct continuous Futures contracts (flag, default: ``True``)
- ``--threads`` Maximum number of threads to use (default is 1)

**Example:**

.. code:: bash

    $ python strategy.py --ibport 4001 --log ~/qtpy/ --blotter MainBlotter --sms +15551230987 ...

.. note::

    **It's recommended that you set the** ``threads`` **parameter based on your strategy's needs and your machine's capabilities!**
    As a general rule of thumb, strategies that are trading a handful of symbols probably don't need to tweak this parameter.

----

Back-Testing Using QTPyLib
---------------------------

In addition to live/paper trading, QTPyLib can also be used for back-testing
**without changing a single line of code**, simply by adding the
following arguments when running your algo.

.. note::

    In order to run back-tests, you **MUST** have the relevant
    historical data either stored in your ``Blotter``'s database or
    as `QTPyLib-compatible CSV files <./workflow.html>`_
    (if using CSV files, you must specify the path using the ``--data`` parameter).

    When backtesting Futures, the Blotter will default to streaming
    adjusted, continuous contracts for the contracts requested, based
    on previously captured market data stored in the Database.

- ``--backtest`` [flag] Work in Backtest mode (default: ``False``)
- ``--start`` Backtest start date (``YYYY-MM-DD [HH:MM:SS[.MS]``)
- ``--end`` Backtest end date (``YYYY-MM-DD [HH:MM:SS[.MS]``)
- ``--data`` Path to the directory with `QTPyLib-compatible CSV files <./workflow.html>`_

With your Blotter running in the background, run your algo from the command line:

.. code:: bash

    $ python strategy.py --backtest --start 2015-01-01 --end 2015-12-31 --data ~/mycsvdata/ --output ~/portfolio.pkl

The resulting back-tested portfolio will be saved in ``~/portfolio.pkl`` for later analysis.

----

Recording Data
--------------

You can record data from within your algo and make this data available as a csv/pickle/h5 file.
You can record whatever you want by adding this to your algo code (bar data is recorded automatically):

.. code:: python

    self.record(key=value, ...)

Then run your algo with the ``--output`` flag:

.. code:: bash

    $ python strategy.py --output path/to/recorded-file.csv


The recorded data (and bar data) will be made available in ``./path/to/recorded-file.csv``,
which gets updated in real-time.

-----

The Instrument Object
---------------------

When writing your algo, an ``Instrument`` Object is passed to each of the algos
methods (``on_tick()``, ``on_bar()``, ``on_quote()`` and ``on_fill()``), which
has many useful `methods and properties <api.html#instrument-api>`_,
including methods to access to the tick/bar/quote data.

Whenever you call ``instrument.get_quotes(...)``, ``instrument.get_ticks(...)`` or ``instrument.get_bars(...)``,
you'll get a Pandas DataFrame (and optionally, a dict object) with the following columns/keys:

* ``asset_class`` (ie. STK, FUT, CASH, OPT, FOP, ...)
* ``symbol`` (ie. ESZ2016_FUT, AAPL, SPX20161024P02150000_OPT, ...)
* ``symbol_group`` (ie. ES_F, AAPL, SPX20161024P, ...)

**Quotes / Ticks will include:**

``bid``, ``bidsize``, ``ask``, ``asksize``, ``last``, ``lastsize``

**Bars will include:**

``open``, ``high``, ``low``, ``close``, ``volume``

**Options (Quotes/Ticks/Bars) will include:**

* ``opt_underlying`` Options' Underlying's Price
* ``opt_dividend`` Options' Underlying Dividend
* ``opt_iv`` Options' Implied Volatility
* ``opt_oi`` Options' Open Interest
* ``opt_price`` Options' Price
* ``opt_volume`` Options' Volume
* ``opt_delta`` Options' Delta
* ``opt_gamma`` Options' Gamma
* ``opt_theta`` Options' Theta
* ``opt_vega`` Options' Vega


.. note::
    See a list of all of ``Instrument`` Object's methods and properties in the
    `Instrument API Reference <api.html#instrument-api>`_.


-----

Instruments Tuples
------------------

When initializing your algo, you're required to pass a list of instruments
you want to trades. List items can be a Ticker Symbol ``String`` (for **US Stocks** only),
and either an IB Contract object or a ``Tuple`` in IB format for all other instruments.

**Example: US Stocks**

.. code:: python

    instruments = [ "AAPL", "GOOG", "..." ]

For anything other than US Stocks, you must use IB Tuples in the
following data information:

``(symbol, sec_type, exchange, currency [, expiry [, strike, opt_type]])``

Where ``expiry`` must be provided for Futures (YYYYMM or YYYYMMDD) and Options (YYYYMMDD)
whereas ``strike`` and ``opt_type`` must be a provided for Options (PUT/CALL).


**Example: UK Stock**

.. code:: python

    instruments = [ ("BARC", "STK", "LSE", "GBP"), (...) ]


**Example: S&P E-mini Futures**

.. code:: python

    instruments = [ ("ES", "FUT", "GLOBEX", "USD", 201609), (...) ]

.. note::
    If you're trading **Front-Month Futures issued by CME-Group**, you can use the
    ``FUT.SYMBOL`` shorthand to have the QTPyLib create the tuple for you (`see more Futures-specific methods here <./futures.html>`_).

    .. code:: python

        instruments = [ "FUT.ES", "FUT.CL", "..." ]


**Example: Netflix Option**

.. code:: python

    instruments = [ ("NFLX", "OPT", "SMART", "USD", 20160819, 98.50, "PUT"), (...) ]


**Example: Forex (EUR/USD)**

.. code:: python

    instruments = [ ("EUR", "CASH", "IDEALPRO", "USD"), (...) ]

-----

For best practice, its recommended that you use the full IB Tuple
structure for all types of instruments:

.. code:: python

    instruments = [
        ("AAPL", "STK", "SMART", "USD", "", 0.0, ""),
        ("BARC", "STK", "LSE", "GBP", "", 0.0, ""),
        ("ES", "FUT", "GLOBEX", "USD", 201609, 0.0, ""),
        ("NFLX", "OPT", "SMART", "USD", 20160819, 98.50, "PUT"),
        ("EUR", "CASH", "IDEALPRO", "USD", "", 0.0, ""),
        ...
    ]

