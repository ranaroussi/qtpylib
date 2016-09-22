Release Notes
=============

*September 22, 2016*

1.4.1a
-------

- Added support for working with Volume based bars (by using ``nV`` in the ``resolution`` parameter)

-----

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

-----

*September 19, 2016*

1.3.97a
-------

- Strategies now have access to IB Account info via ``self.account``
- Added support for ``Fill-or-Kill`` and ``Iceberg`` orders (see API docs)
- Automatic re-reconnection to TWS/GW when connection lost

