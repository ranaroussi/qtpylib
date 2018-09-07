Futures Trading
===============

Auto-Tuple Generation
---------------------

The ``futures.make_tuple(...)`` method automatically
constructs a valid instrument tuple for any Futures
contract available on Interactive Brokers, using the information available
via the `contract specification retrieval functionality <#contract-specification>`_.

.. code:: python

    # strategy.oy
    ...

    from qtpylib import futures

    if __name__ == "__main__":
        strategy = MyStrategy(
            instruments = [
                futures.make_tuple("ES", 201612),
                futures.make_tuple("CL", 201612),
                futures.make_tuple("GBL", 201612, exchange="DTB")
            ],
            ...
        )

    ...


-----


Most Traded Contract Expiration
-------------------------------

If you want to **always trade the most active Futures contract**
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

        strategy = MyStrategy(
            instruments = [ ("ES", "FUT", "GLOBEX", "USD", ACTIVE_MONTH, 0.0, "") ],
            ...
        )

        ...

You can now achieve the same functionality by using a simple shorthand as the instrument symbol.
In this case

.. code:: python

    # strategy.oy
    ...

    # from qtpylib import futures
    # ^^ no need to import this when using this method

    strategy = MyStrategy(
        instruments = [ "FUT.ES" ],
    )

    ...


.. note::
    This functionality currently only works for the CME Group's futures (inc. CME, GLOBEX, CBOT, NYMEX, and COMEX).


-----


Contract Specification
----------------------

When you want to know a Futures contract's margin requirements, you can
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
        'intraday_initial': 2250.0,
        'intraday_maintenance': 1800.0,
        'overnight_initial': 4500.0,
        'overnight_maintenance': 3600.0,
        'symbol': 'NQ'
    }

    """

\* To get the maximum number of contracts you can trade,
based on your account balance and contract requirements,
use ``instrument.get_margin_max_contracts()``
from within your strategies.

