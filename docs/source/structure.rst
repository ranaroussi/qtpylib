Library Structure
=================

There are 5 main components to QTPyLib:

1. ``Blotter`` - handles market data retreival and processing.
2. ``Broker`` - sends and proccess orders/positions (abstracted layer).
3. ``Algo`` - (sub-class of ``Broker``) communicates with the ``Blotter`` to pass market data to your strategies, and proccess/positions orders via ``Broker``.
4. ``Reports`` - provides real time monitoring of trades and open opsitions via Web App, as well as a simple REST API for trades, open positions and market data.
5. Lastly, **Your Strategies**, which are sub-classes of ``Algo``, handle the trading logic/rules. This is where you'll write most of your code.

-----

Flow Chart
----------

.. image:: _static/diagram.png
    :width: 640px
    :align: center
    :alt: QTPyLib Diagram
