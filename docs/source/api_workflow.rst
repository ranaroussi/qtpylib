Workflow API
------------

.. autofunction:: qtpylib.workflow.get_data_ib(...)

.. autofunction:: qtpylib.workflow.prepare_data(...)

.. note::

    The ``colsmap`` parameter structure expect a ``dict`` that maps
    QTPyLib's columns names with the one used by your DataFrame.

    The dict should be in the following structure:
    ``"qtpylib_column_name": "your_column_name"``,
    which any missing ``colsmap`` key is assumed to use the same name as QTPyLib's.
    For example:

    .. code:: python

        from qtpylib import workflow

        newdf = workflow.prepare_data("AAPL", data=df,
            colsmap={'open':'O', 'high':'H', 'low':'L', 'close':'C', 'volume':'V'})


    - **QTPyLib's columns are:**
        open, high, low, close, volume
    - **QTPyLib's Options' data also include:**
        opt_price, opt_underlying, opt_dividend, opt_volume, opt_iv, opt_oi, opt_delta, opt_gamma, opt_vega


.. autofunction:: qtpylib.workflow.store_data(...)
