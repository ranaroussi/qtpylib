Release Notes
=============

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

