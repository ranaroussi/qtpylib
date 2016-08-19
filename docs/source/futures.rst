Futures Trading
===============

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


