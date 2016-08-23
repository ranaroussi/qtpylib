Futures Trading
===============

Most Traded Contract Expiration
-------------------------------

If you want to **always trade the most active future contract**
(based on the previous day's volume and open interest),
you can do so by using the ``futures.get_active_contract()``
function to construct your IB contract tuples specified in your algo.

.. code:: python

    # strategy.oy
    ...

    from qtpylib import futures

    if __name__ == "__main__":
        # get most active ES contract
        ACTIVE_MONTH = futures.get_active_contract("ES")

        strategy = CrossOver(
            instruments = [ ("ES", "FUT", "GLOBEX", "USD", ACTIVE_MONTH, 0.0, "") ],
            ...
        )

        ...

.. note::
    This functionality currently works for future contracts traded on
    the CME only (including CME, GLOBEX, CBOT, NYMEX and COMEX).


-----


Contract Margin Requriments
---------------------------

When you want to know a futures contract's margin requirements, you can
call ``futures.get_ib_margin(...)`` to get that information.
New data is fetched from IB id cache file doesn't exist or
if it's older than 24 hours.

.. code:: python

    # strategy.oy
    ...

    from qtpylib import futures

    def on_bar(self, instrument):
        margin = futures.get_ib_margin('path/to/cache_file.pkl', "NQ", "GLOBEX")

        if margin['intraday_initial'] > self.account['AvailableFunds']:
            print("Not enough funds to trade this contract")
            return


    """
    margin returns a dict with the following data:

    {
        'class': 'NQ',
        'currency': 'USD',
        'description': 'E-mini NASDAQ 100 Futures',
        'exchange': 'GLOBEX',
        'has_options': True,
        'intraday_initial': 2250.0,
        'intraday_maintenance': 1800.0,
        'overnight_initial': 4500.0,
        'overnight_maintenance': 3600.0,
        'symbol': 'NQ'
    }

    """

This information is also available using
``instrument.get_futures_margin_requirement()``
from within your strategies (in this case, the
cache file will be saved as ``ib_margins.pkl``
in your working directory).
