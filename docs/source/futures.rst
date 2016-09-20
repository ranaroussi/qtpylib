Futures Trading
===============


Minimum Contract Tick Size
--------------------------

When using a trailing stop order, you're required to specify the
``ticksize`` of the contract you're trading in order to round the
trailing stop to the closest valid price, based on the contract's
minimum price fluctuation.

**For Example:**
You're trading the S&P E-mini Futures and you've specified that the
traling stop should be 0.2% below the current price. Without specifying
the ``ticksize`` information, the stop order's price will come out as
in a stop order of **2,188.3645** when the contract's trading at
**2,192.75**  -- *which will result in a rejected order*.

By using **0.25** as the ``ticksize``, the stop order will be
rounded down to **2,188.25**, which is a valid price for the ES.

You can pass the tick size manually (ie. 1.0 for YM, 0.25 for ES,
0.01 for CL), or you can use the ``futures.get_contract_ticksize()``
method to pull this information automatically from the CME's website.

.. code:: python

    # strategy.oy
    ...

    from qtpylib import futures

    def on_start(self):
        # self.ticksize = 0.25
        self.ticksize = futures.get_contract_ticksize("ES")

    def on_bar(self, instrument):
        ...
        instrument.buy(1,
            ticksize = self.ticksize,
            target = tick['last'] + 2,
            initial_stop = tick['last'] - 2,
            trail_stop_by = 0.2 # in percent = 0.2%
        )
        ...

.. note::
    * This functionality currently only works for the CME Group's futures (inc. CME, GLOBEX, CBOT, NYMEX and COMEX).
    * The default ticksize is 0.01, so this parameter isn't required for contracts with 0.01 min. price fluctuation.
    * Refer to the `Instruments API <./api.html#qtpylib.instrument.Instrument.order>`_ for more information.

-----


Most Traded Contract Expiration
-------------------------------

If you want to **always trade the most active future contract**
(based on the previous day's volume and open interest),
you can do so by using the ``futures.get_active_contract()``
function to construct your IB contract tuples specified in
your algo.

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
    This functionality currently only works for the CME Group's futures (inc. CME, GLOBEX, CBOT, NYMEX and COMEX).


-----


Margin Requriments for Contract
-------------------------------

When you want to know a futures contract's margin requirements, you can
call ``futures.get_ib_futures(...)`` to get that information.
New data is fetched from IB id cache file doesn't exist or
if it's older than 24 hours.

.. code:: python

    # strategy.oy
    ...

    from qtpylib import futures

    def on_bar(self, instrument):
        contract_spec = futures.get_ib_futures("NQ", "GLOBEX")

        if contract_spec['intraday_initial'] > self.account['AvailableFunds']:
            print("Not enough funds to trade this contract")
            return


    """
    contract_spec returns a dict with the following data:

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

To get the maximum number of contracts you can trade,
based on your account balance and contract requirements,
use ``instrument.get_margin_max_contracts()``
from within your strategies.

