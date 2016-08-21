Writing Your Algorithm
======================

When creating your algorithm, there are two functions that handles
incoming market data from the running Blotter. These are
``on_tick()`` which is invoked on every tick captured, and
``on_bar()``, which is invoked on every bar created in the
pre-specified resolution. An `Instruments Object <./api_instrument.html>`_ is being passed
to each method when called.

If your algo does't need/work with tick data ommit the ``on_tick()``
function from your code.


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

        def on_bar(self, instrument):
            # buy if position = 0, sell if in position > 0
            if instrument.positions['position'] == 0:
                instrument.buy(100)
            else:
                instrument.exit()


    if __name__ == "__main__":

        # initilize the algo
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

        def on_tick(self, instrument):
            pass

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
            instruments = [ ("CL", "FUT", "NYMAX", "USD", 201609) ],
            resolution  = "1H"
        )

        strategy.run()


With your Blotter running in the background, run your algo from the command line:

.. code:: bash

    $ python strategy.py --log ~/qtpy/


By adding ``--log ~/qtpy/`` we ask that the resulting trade journal be saved
in ``~/qtpy/STRATEGY_YYYYMMDD.csv`` for later analysis **in additioan** to
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
                ("CL", "FUT", "NYMAX", "USD", 201609)
            ],
            resolution  = "15T"
        )

        strategy.run()

-----

Available Arguments
-------------------

Below are all the parameters that can either be set via the ``Algo()``
or via CLI (**all are optional**).

Algo Parameters
~~~~~~~~~~~~~~~

- ``instruments`` List of stock symbols (for US Stocks) / IB Contract Tuples
- ``resolution`` Bar resolution (pandas resample resolution: 1T/4H/etc, and K for tick bars).
- ``tick_window`` Length of tick lookback window to keep (defaults to 1)
- ``bar_window`` Length of bar lookback window to keep (defaults to 100)
- ``timezone`` Convert IB timestamps to this timezone, eg. "US/Central" (defaults to UTC)
- ``preload`` Preload history upon start (eg. 1H, 2D, etc, or K for tick bars).
- ``blotter`` Log trades to MySQL server used by this Blotter (default: ``auto-detect``).

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

- ``--sms`` List of numbers to text orders (default: ``None``)
- ``--log`` Path to store trade data (default: ``None``)
- ``--ibport`` IB TWS/GW Port to use (default: ``4001``)
- ``--ibclient`` IB TWS/GW Client ID (default: ``998``)
- ``--ibserver`` IB TWS/GW Server hostname (default: ``localhost``)
- ``--blotter`` Log trades to MySQL server used by this Blotter (default: ``auto-detect``)
- ``--output`` Path to save the recorded data (default: ``None``)

**Example:**

.. code:: bash

    $ python strategy.py --ibport 4001 --log ~/qtpy/ --blotter MainBlotter --sms +15551230987 ...

----

Back-Testing Using QTPyLib
---------------------------

In addition to live/paper trading, QTPyLib can also be used for back-testing
**without changing event one line of code**, simply by adding the
following arguments when running your algo.

.. note::
    You **MUST** have the relevant historical data stored in your
    Blotter's database in order to run back-tests - which is also
    a good reason to keep your Blotter running for all eternity :)

    In addition, when backtesting Futures, the Blotter will stream
    adjusted, continous contracts for the contracts requested, based
    on previously captured market data stored in the Database.

- ``--backtest`` [flag] Work in Backtest mode (default: ``False``)
- ``--start`` Backtest start date (``YYYY-MM-DD [HH:MM:SS[.MS]``)
- ``--end`` Backtest end date (``YYYY-MM-DD [HH:MM:SS[.MS]``)

With your Blotter running in the background, run your algo from the command line:

.. code:: bash

    $ python strategy.py --backtest --start 2015-01-01 --end 2015-12-31 -output portfolio.pkl

The resulting back-tested portfolio will be saved in ``./portfolio.pkl`` for later analysis.


Recording Data
--------------

You can record data from within your algo and make this data available as a csv/pickle/h5 file.
You can record whatever you want by adding this to your algo code (bar data is recorded automatically):

.. code:: python

    self.record(key=value, ...)

Then run your algo with the ``--output`` flag:

.. code:: bash

    $ python strategy.py --output path/to/recorded-file.csv


The recorded data (and bar data) will be made availble in ``./path/to/recorded-file.csv``,
which gets updated in real-time.


-----

Initilizing Parameters
----------------------

Sometimes you'd want to set some parameters when you initlize
your Strategy. To do so, simply add an ``initilize()`` method
to your strategy, and set your parameters there. It will be
invoked once when you strategy starts.


.. code:: python

    # strategy.py
    from qtpylib.algo import Algo

    class MyStrategy(Algo):

        def initilize(self):
            self.paramA = "a"
            self.paramB = "b"
            ...


Instruments Tuples
------------------

When initilizing your algo, you're required to pass a list of instruments
you want to trades. List items can be a Ticker Symbol ``String`` (for **US Stocks** only)
or an ``Tuple`` in IB format for other instruments.

**Example: US Stocks**

.. code:: python

    instruments = [ "AAPL", "GOOG", "..." ]

For anything other than US Stocks, you must use IB Tuples in the
following data information:

``(symbol, sec_type, exchange, currency [, expiry [, strike, opt_type]])``

Where ``expiry`` must be provided for Futures (YYYYMM) and Options (YYYYMMDD)
whereas ``strike`` and ``opt_type`` must be a provided for Options (PUT/CALL).


**Example: UK Stock**

.. code:: python

    instruments = [ ("BARC", "STK", "LSE", "GBP"), (...) ]


**Example: S&P E-mini Futures**

.. code:: python

    instruments = [ ("ES", "FUT", "GLOBEX", "USD", 201609), (...) ]


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

