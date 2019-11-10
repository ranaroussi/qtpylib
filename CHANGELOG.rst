Release Notes
=============

*November 10, 2019*

1.5.84
-----------
- Hot fix by @aspenforest - fixed pip installer

*February 13, 2019*

1.5.83
-----------
- Fix numpy transpose error in stoch indicator
- Fix reports' ``KeyError`` under Python 3.7+ when not using ``--nopass``
- Fix reports' static file error with incorrect path

*January 11, 2019*

1.5.82
-----------
- Set strategy's logging level to ``INFO``
- Suppress SQL messages when using ``--dbskip``
- Added option to set trailing stop offset type by specifiying ``trail_stop_type``. Options are: **amount** and **percent** (default)
- Defaults to single threaded mode unless otherwise specified
- Requires ezIBpy >= 1.12.66
- Lots of bugfixes, and code improvements

*September 17, 2018*

1.5.81
-----------
- Added official support for Python 3.7
- Removed Google and Yahoo data retrieval methods from ``Workflow``
- Added auto-resample option to ``Workflow.prepare_data``
- Fixed backtesting issues related to sometimes not logging positions
- Lots of bugfixes, and code improvements


*September 12, 2018*

1.5.80
-----------
- Fixed issues related to multi-instrument strategies
- Misc fixed typos, bugfixes, and code improvements


*September 7, 2018*

1.5.79
-----------
- Changed license to Apache License 2.0
- Trailing stop compared against 0 instead of None
- Fix prices to comply with contract's min-tick
- Fixed IB futures margin fetcher
- Fixed CME scraping and active contract parser
- Avoid sending empty tick/bars to algo
- Updated code to work with latest version of Pandas
- Fixed compatibility with the ezIBpy v1.12.62
- Misc fixed typos, bugfixes, and code improvements

*July 26, 2018*

1.5.78
-----------
- Fixed compatibility with the ezIBpy v1.12.58
- Pushed develop branch to master

*January 12, 2018*

1.5.77
-----------
- Check for ``dbskip`` on ``Blotter.mysql_connect()`` (issue 75)
- Changed numpy.std() estimator bias (ddof = 1)
- Fixed Heiken-Ashi bar calculation
- Added Zero-lag SMA/EMA/HMA
- Misc bugfixes and code improvements


*September 25, 2017*

1.5.76
-----------
- Fixed possible miscalculation of local machine's timezone (hotfix)

1.5.75
-----------
- Futures spec is now downloading from `qtpylib.io <http://qtpylib.io/resources/futures_spec.csv>`_ (updated daily)
- Technical indicators made faster
- Added ``tools.multi_shift`` method to for shifting multiple rows in Pandas DataFrames
- Misc bugfixes and code improvements

*July 26, 2017*

1.5.74
-----------
- Checks for ``Python >= 3.4`` before running
- Requires ``ezIBpy >= 1.12.56``
- Option to group contracts togther (groundwork for spreads / combo orders)
- Allows to add contracts/symbols to ``Algo`` *after* initialization via ``Broker.add_instruments(...)``
- ``Algo`` instruments now accepts IB Contracts as instruments
- Instrument's ``get_ticks()`` and ``get_bars()`` returns ``None`` when empty and reqested in ``dict`` format
- Added ``instrument.get_price()`` and ``instrument.price`` (returns current market price)
- Added ``instrument.pnl_in_range(min, max)`` method to the instrument object
- Added ``TotalPNL`` to the portfolio object (``unrealizedPNL + realizedPNL``)
- Added option to get timezone as delta in ``tools.get_timezone()``
- Better Heikin-Ashi candle formula (fixed first candle's open calculation)
- Improved Stochastic indicator
- Added Awesome Oscillator indicator
- Added TDI (Traders Dynamic Index) indicator
- Added ``crossed()`` indicator (returns ``True`` if first series crosses above or below second series)
- Crossing indicators/methods works with numbers as 2nd series (ie ``bars['close'].crossed_above(30)``)
- Misc bugfixes, code improvements, cleanup and abstraction


*May 7, 2017*

1.5.73
-----------
- Requires ezIBpy >= 1.12.51

1.5.72
-----------
- Better PEP8 compliance
- Checking for Python version >= 3.4
- Upgraded to Twilio version >= 6.0.0
- Improved Stochastic indicator
- Added Awesome Oscillator and TDI indicators
- Misc bugfixes, code improvements, cleanup and abstraction


*March 25, 2017*

1.5.71
-----------
- Fixed ``pip`` installer

1.5.7
-----------
- Fixed minor bug in machine timeozone detection

*February 26, 2017*

1.5.6
-----------
- Added 2 Indicators: PVT (Price Volume Trend) and Z-Score
- Fixed resample bug when using local timezones (merge pull request #55)

*February 6, 2017*

1.5.59
-----------
- Requires ezIBpy >= 1.12.45 (fixes a few open issues)

*December 31, 2016*

1.5.58
-----------
- Misc bugfixes, code improvements, cleanup and abstraction

*December 30, 2016*

1.5.57
-----------
- Bugfixes and code cleanup

1.5.56
-----------

- Max # of threads is set to 1 (single-threaded) by default and can be changed using the ``max_threads`` run-time parameter  in ``Blotter()`` and ``Algo()``. **It's recommended that you set this parameter based on your strategy's needs and your machine's capabilities** (strategies trading a handful of symbols probably won't need to tweak this parameter).


*December 25, 2016*

1.5.55a
-----------

- Threading-related code improvements: ``tools.resample()`` syncs last timestamp of all symbols; ``add_stale_tick()`` checks for real tick with same index before triggering ``_tick_handler()``
- ``Instrument`` object not defaults to strategy's ``bar_window`` and ``tick_window`` if no window specified (to get full bar window, use ``instrument.get_bars()`` or simply ``instrument.bars``)

*December 22, 2016*

1.5.54a
-----------
- ``add_stale_tick()`` made thread-safer

1.5.53a
-----------
- ``Blotter`` market data handlers now using threaded, non-blocking architecture.
- Misc bugfixes, code improvements, cleanup and abstraction


*December 21, 2016*

1.5.52a
-----------
- All market data events are now asynchronous / non-blocking
- Misc bugfixes, code improvements, cleanup and abstraction


*December 20, 2016*

1.5.51a
-----------

- Minor bugfixes, code improvements, cleanup and abstraction

1.5.50a
-----------

- Minor bugfixes, code improvements, cleanup and abstraction

*December 19, 2016*

1.5.49a
-----------

- Fixed bugs that may occur on multi-instrument strategies
- Misc code improvements, cleanup and abstraction

*December 18, 2016*

1.5.48a
-----------

- Bugfixes

1.5.47a
-----------

- Introduced an **all new** ``Workflow`` module for downloading, cleaning, preparing and uploading market data to the database
- Backtesting can now be done using CSV files (converted into a QTPyLib-compatible format using the ``Workflow`` module)
- Misc bugfixes and code improvements, cleanup and abstraction
- Requires ezIBpy >= 1.12.44

*December 12, 2016*

1.5.46a
--------

- Bugfixes

*December 11, 2016*

1.5.45a
--------

- ``Blotter`` automatically backfills missing historical data for back-testing (based on the ``start`` and ``end`` parameters) and live-trading (based on the ``preload`` parameter)
- Better local timezone detection
- Requires ezIBpy >= 1.12.42
- Misc bugfixes and code improvements/cleanup


**Note regarding backfilling:**
Backfilling is currently supported for strategies with 1-minute or higher resolution.
Historical data availability is subject to `Interactive Brokers Historical Data Limitation <https://www.interactivebrokers.com/en/software/api/apiguide/tables/historical_data_limitations.htm>`_.


*December 7, 2016*

1.5.44a
--------
- Changed to lowercase ``utf-8`` encoding in file's header


*December 6, 2016*

1.5.43a
--------
- Fixed bug introduced in version ``1.5.42a``

1.5.42a
--------
- Forcing expiry in ``symbols.csv`` to be stored as ``int``

1.5.41a
--------
- Fixed bug in ``Blotter.log2db()`` (closing issue #36)
- Fixed multi-instrument strategy initialization (closing issues #37 + #38)
- Misc bugfixes and code improvements/cleanup


*December 4, 2016*

1.5.40a
--------
- Fixed bug that caused ``Blotter`` to store data in MySQL before timezone was set (possibly resulting in out-of-sequence time-series for historical data) by ignoring the captured first tick.
- ``Blotter`` now removes out-of-sequence ticks/bars from historical data (should fix ``issue #31``)
- Misc bugfixes and code improvements/cleanup


*December 1, 2016*

1.5.39a
--------
- Portfolio playing nice with multi-symbol portfolios
- Cleanup portfolio data before saving
- Implemented shorter delay and more elegant code in ``Blotter.drip()`` (used by the backtester)
- ``force_res`` is now always on for time-based bars
- Renamed ``Blotter.listen()`` to ``Blotter.stream()``
- Misc bugfixes and code improvements

*November 29, 2016*

1.5.38a
--------
- ``load_blotter_args()`` moved to ``Broker`` class file to be used by clients
- ``Broker.get_portfolio()`` now returns empty portfolio object as default when symbol is specified
- ``Reports`` uses unified logger and arg parsing
- Misc bugfixes and code improvements
- Requires ezIBpy >= 1.12.41

*November 22, 2016*

1.5.37a
--------

- Fixed ``Broker`` logging initilizer
- Requires ezIBpy >= 1.12.39 (solves misc issues with expired contracts)

1.5.36a
--------

- Blotter saves expiration dates for Futures and Options based on ezIBpy's ``contractDetails()`` data

1.5.35a
--------

- Misc bugfixes and code improvements
- Requires ezIBpy >= 1.12.38


*November 21, 2016*

1.5.34a
--------

- Fix parsing of contract expiration

*November 16, 2016*

1.5.33a
--------

- Fixed command line agrument parsing issues
- All params in ``Algo()`` and ``Blotter()`` are now explicit and are overridden in runtime using command line arguments
- Make sure expiry values aren't decimals
- Requires ezIBpy >= 1.12.36
- Renamed ``force_resolution`` to ``force_res`` in ``Algo()``
- Using unified logging from latest ``ezIBpy`` (use ``self.log.LEVEL(...)`` instead of ``loggig.LEVEL(...)`` in your strategies)
- Misc bugfixes and code improvements


*November 15, 2016*

1.5.32a
--------

- Set ``ticksize`` to ``0`` for stale ticks (for when using ``"force_resolution" = True``)


*November 13, 2016*

1.5.31a
--------

- Requires ezIBpy >= 1.12.32
- Added support for ``tif`` (time in force) parameter in order creation. Options are: ``DAY`` (default), ``GTC``, ``IOC`` and ``GTD``.


*November 12, 2016*

1.5.30a
--------

- Requires ezIBpy >= 1.12.31
- Added ``instrument.get_contract_details()`` and ``instrument.tickerId()`` methods (see API reference section in docs for more info)
- ``futures.get_contract_ticksize()`` marked as deprecated (``instrument.get_ticksize()`` or ``instrument.ticksize`` instead)
- Ignoring ``ticksize`` parameter in ``order()`` (ezIBpy's auto detects min. tick size based on contract spec.)

1.5.29a
--------

- Interval-based bars are now tread-safe and working correctly when ``"force_resolution" = True``


*November 11, 2016*

1.5.28a
--------

- Fixed a bug that prevented backtesting second-level resolution strategies

1.5.27a
--------

- Introduced ``force_resolution`` parameter in ``Algo`` to force a new bar on every ``resolution`` even if no new ticks received (default is False)

1.5.26a
--------

- Fixed parsing of flag params (related to issue #17)


*November 10, 2016*


1.5.25a
--------

- Fixed bar events in backtesting mode to fire every 250ms instead of 2.5s (closing issue #21)
- Fixed parsing of ``backtest`` param in ``Algo`` (closes issue #17)


1.5.24a
--------

- Fixed issue that caused errors when bar resolution was set to seconds (closing issue #18)


1.5.23a
--------

- Requires ezIBpy >= 1.12.29
- ``Blotter`` uses refactored logging in ezIBPy 1.12.29


*November 9, 2016*

1.5.22a
--------

- ``Blotter`` and ``Algo`` now accepts all command-line arguments as ``__init()__`` parameters (closing issue #17)


*November 8, 2016*

1.5.21a
--------

- Blotter logs warnings and errors sent by TWS/GW


1.5.2a
--------
- Upped version number due to malformed submission to PyPi (1.5.1)


1.5.1a
--------

- Wait 5ms before invoking ``on_fill()`` to allow portfolio to sync from TWS/GW
- Renamed Instrument object's ``margin_max_contarcts()`` to ``max_contracts_allowed()``
- Added ``get_bar()`` and ``get_tick()`` methods to Instrument object (as well as ``tick`` and ``bar`` properties)
- Misc bugfixes and code improvements


*November 6, 2016*

1.5.0a
--------

- Added ``move_stoploss()`` to instrument object. This method auto-discover **orderId** and **quantity** and invokes ``self.modify_order(...)``
- Fixed bug that prevented modification of stop orders using ``modify_order(...)``
- Fixed rederence to renamed and modified method (``active_order_id`` => ``active_order``)

1.4.99a
-------

- Using the new ``IbPy2``'s PyPi installer; no separate install of ``IbPy`` is required
- Using latest ``ezIBpy`` (now also using ``IbPy2``)


*November 2, 2016*

1.4.98a
-------

- Added support for Orderbook-based strategies via ``on_orderbook(...)`` (requires the ``--orderbook`` flag to be added to Blotter)
- Added bar(s), tick(s), quote and orderbook properties to the ``Instrument`` object


*October 25, 2016*

1.4.97a
-------

- Made changes to ``.travis.yml`` to help Travis-CI with its Pandas build issues


1.4.96a
-------

- Creating synthetic ticks for instruments that DOESN'T receive ``RTVOLUME`` events (issue #9)
- ``futures.make_tuple(...)`` auto selects most active contract when no expiry is provided (CME Group Futures only)
- Misc bugfixes and code improvements


*October 24, 2016*

1.4.95a
-------

- Removed debugging code

1.4.94a
-------

- Fixed bug caused by ``self.record`` (closing issue #12)
- Misc bugfixes and code improvements


*October 23, 2016*

1.4.93a
-------

- Bugfix: Updated backtesting mode to use correct variable names (closing issue #10)


*October 21, 2016*

1.4.92a
-------

- Full support for Options trading (greeks available upon quotes, ticks and bars)
- Improved asset class and symbol group parsing
- QTPyLib's version is now stored in MySQL for smooter upgrades
- ``pip`` Installer requires ezIBpy >= 1.12.23
- Misc bugfixes and code improvements


*October 18, 2016*

1.4.91a
-------

- Misc bugfixes

1.4.9a
-------

- Continuous Futures contract construction is now optional (defaults to ``True``)
- Added ``futures.make_tuple(...)`` for automatic tuple construction for Futures


*October 14, 2016*

1.4.8a
-------

- Using a **synthetic tick** for CASH contracts (cash markets do not get RTVOLUME)


*September 30, 2016*

1.4.7a
-------

- Fixed issue that prevented from blotter to assign ``asset_class`` to stocks


*September 29, 2016*

1.4.6a
-------

- Rounding numbers in SMS message template


*September 28, 2016*

1.4.5a
-------

- Fixed sms formatting by sending SMS before logging trade


*September 27, 2016*

1.4.4a
-------

- Added open trades + unrealized PNL to ``instrument.trades`` and ``instrument.get_trades()``
- Switched DataFrame length check to ``len(df.index)>0`` (faster than ``df.empty`` or ``len(df)>0`` in my checks)
- Fixed last price in recent orders


*September 26, 2016*

1.4.3a
-------

- Introduced ``instrument.trades`` / ``instrument.get_trades()`` as quick access to the instuments trade log

1.4.2a
-------

- Updated pip installer to use ezIBpy >= 1.12.19


*September 22, 2016*

1.4.1a
-------

- Added support for working with Volume based bars (by using ``nV`` in the ``resolution`` parameter)


*September 20, 2016*

1.4.0a
-------

- Fixed setup import to prevent built error

1.3.99a
-------

- Added option to send limit stop orders

1.3.98a
-------

- ``tools.round_to_fraction()`` now auto detects decimals based on resoution rounder
- Fixed Eurodollar's base url in ``futures.py``
- Fetching correct ticksize for futures (including those that aren't using decimal ticks, eg 1/32 for bonds)


*September 19, 2016*

1.3.97a
-------

- Strategies now have access to IB Account info via ``self.account``
- Added support for ``Fill-or-Kill`` and ``Iceberg`` orders (see API docs)
- Automatic re-reconnection to TWS/GW when connection lost

