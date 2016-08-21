Technical Indicators
====================

Although you can import technical indicator libraries such as the
excellent `TA-Lib <http://ta-lib.org>`_ and use them in your strategies,
QTPyLib does comes bundled with some common indicators that work as Pandas Objects.

ATR
---

.. code:: python

    bars['atr'] = bars.atr(window=14 [, exp=False])
    ...


Bollinger Bands
---------------

.. code:: python

    bb = bars.bollinger_bands(window=20, stds=2)

    bars['bb_upper'] = bb['upper']
    bars['bb_lower'] = bb['lower']
    bars['bb_mid']   = bb['mid']
    ...


Weighted Bollinger Bands
~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: python

    wbb = bars.weighted_bollinger_bands(window=20, stds=2)

    bars['wbb_upper'] = wbb['upper']
    bars['wbb_lower'] = wbb['lower']
    bars['wbb_mid']   = wbb['mid']
    ...


CCI
---------------------------

.. code:: python

    bars['cci'] = bars.cci(window=14)
    ...


Crossed Above/Below
-------------------

.. code:: python

    bars['sma'] = bars['close'].rolling_mean(10)

    if bars['close'].crossed_above(bars['sma']):
        ...

    if bars['close'].crossed_below(bars['sma']):
        ...


IBS
---------------------------

.. code:: python

    bars['ibs'] = bars.ibs()
    ...


Implied Volatility
---------------------------

.. code:: python

    bars['iv'] = bars.implied_volatility(window=252)
    ...


Keltner Channel
---------------------------

.. code:: python

    kc = bars.keltner_channel(window=14, atrs=2)

    bars['kc_upper'] = kc['upper']
    bars['kc_lower'] = kc['lower']
    bars['kc_mid']   = kc['mid']
    ...


MACD
---------------------------

.. code:: python

    macd = bars.macd(fast=3, slow=10, smooth=16)

    bars['macd']        = macd['macd']
    bars['macd_signal'] = macd['signal']
    bars['macd_hist']   = macd['histogram']
    ...


Moving Average
--------------

Simple Moving Average
~~~~~~~~~~~~~~~~~~~~~

Shorthand for ``bars.rolling_mean(...)``

.. code:: python

    bars['sma'] = bars.sma(window=200 [, min_periods=None])
    ...


Weighted Moving Average
~~~~~~~~~~~~~~~~~~~~~~~

Shorthand for ``bars.rolling_weighted_mean(...)``

.. code:: python

    bars['wma'] = bars.wma(window=200 [, min_periods=None])
    ...


Hull Moving Average
~~~~~~~~~~~~~~~~~~~

Shorthand for ``bars.hull_moving_average(...)``

.. code:: python

    bars['hma'] = bars.hma(window=200 [, min_periods=None])
    ...



Price Indicators
----------------

Mid: (High + Low) / 2
~~~~~~~~~~~~~~~~~~~~~~
.. code:: python

    bars['mid'] = bars.mid_price()
    ...


Typical: (High + Low + Close) / 3
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. code:: python

    bars['typical'] = bars.typical_price()
    ...




Rolling Indicators
------------------

Min
~~~

.. code:: python

    bars['min'] = bars.rolling_min(window=14 [, min_periods=None])
    ...


Max
~~~

.. code:: python

    bars['max'] = bars.rolling_max(window=14 [, min_periods=None])
    ...


Mean
~~~~

.. code:: python

    bars['sma'] = bars.rolling_mean(window=200 [, min_periods=None])
    ...


Standard Deviation
~~~~~~~~~~~~~~~~~~

.. code:: python

    bars['std'] = bars.rolling_std(window=200 [, min_periods=None])
    ...


Weighted Mean
~~~~~~~~~~~~~

.. code:: python

    bars['wma'] = bars.rolling_weighted_mean(window=200 [, min_periods=None])
    ...



Returns
-------

.. code:: python

    bars['returns'] = bars.returns()
    ...


Log Returns
~~~~~~~~~~~

.. code:: python

    bars['log_returns'] = bars.log_returns()
    ...



ROC
---------------------------

.. code:: python

    bars['roc'] = bars.roc(window=14)
    ...


RSI
---------------------------

.. code:: python

    bars['rsi'] = bars.rsi(window=14)
    ...



Session
---------------------------

This isn't an indicator, but rather a utility that trims
the bars to a specified "Session" (useful when wanting to
work, for example, with the most recent PIT or GLOBEX
session to calculate VWAP, etc.).

.. code:: python

    # make sure to specity timezone="US/Central" for your algo
    # otherwise, the default timezone is UTC

    # pit session
    bars = bars.session(start='08:30', end='15:15')

    # globex session
    bars = bars.session(start='17:00', end='16:00')
    ...


Stochastics
---------------------------

.. code:: python

    bars['stoch'] = bars.stoch(window=14, slow=False, slow_ma=3)
    ...



True Range
---------------------------

.. code:: python

    bars['tr'] = bars.true_range()
    ...


VWAP
----

.. code:: python

    bars['vwap'] = bars.vwap(bars)
    ...

