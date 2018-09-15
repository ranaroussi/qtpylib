Data Workflow
=============

QTPyLib's new ``workflow`` module includes some handy methods for
working with external data sources when backtesting.

Working with External Data
--------------------------

Sometimes, you'd want to backtest your strategies using market data
you already have from sources other than the ``Blotter``.
Before you can use market data from external data sources,
you'll need to convert it into a QTPyLib-compatible data format.

Once the data is converted, it can be read by your strategies as CSV files.
You can also save the converted data in your ``Blotter``'s MySQL database
so it can be used just like any other data captured by your ``Blotter``.

**Code Example:**

.. code:: python

    # load the workflow module
    from qtpylib import workflow as wf

    # Load some data from Quandl
    import quandl
    aapl = quandl.get("WIKI/AAPL", authtoken="your token here")

    # convert the data into a QTPyLib-compatible
    # data will be saved in ~/Desktop/AAPL.BAR.csv
    df = wf.prepare_data("AAPL", data=aapl, output_path="~/Desktop/")

    # store converted bar data in MySQL
    # optional, requires a running Blotter
    wf.store_data(df, kind="BAR")


.. note::

    The first argument in ``prepare_data()`` must be a **valid string as IB tuple**
    (just like the those specified in your strategy's ``instruments`` parameter).
    For a complete list of available methods and parameters for each
    method, please refer to the `Workflow API <./api.html#workflow-api>`_
    for a full list of available parameters for each method.


Using CSV files when Backtesting
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Once you have your CSV files in a QTPyLib-compatible format,
you can backtest using this data using the ``--data`` flag when
running your backtests, for example:

.. code:: bash

    $ python strategy.py --backtest --start 2015-01-01 --end 2015-12-31 --data ~/mycsvdata/ --output ~/portfolio.pkl

Please refer to `Back-Testing Using QTPyLib <./algo.html#back-testing-using-qtpylib>`_
for more information about back-testing using QTPyLib.

