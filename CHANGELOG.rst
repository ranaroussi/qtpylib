Release Notes
=============

*November 10, 2016*

1.5.26a
-------
- Add Algo.with_cmd_args() factory to handle command line arguments cleanly and explicitly.
- Call Algo.on_start() from run() rather than __init__() so fields set in __init__ are available
  to on_start() in subclasses.

1.5.25a
--------

- Fixed bar events in backtesting mode to fire every 250ms instead of 2.5s (closing issue #21)
- Fixed parsing of ``backtest`` param in ``Algo`` (closes issue #17)


1.5.24a
--------

- Fixed issue that caused errors when bar resolution was set to seconds (closing issue #18)


1.5.23a
--------

- Require ezIBpy >= 1.12.29
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

