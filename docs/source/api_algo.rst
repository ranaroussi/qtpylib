Algo API
--------

Algo is a Sub-Class of Broker and the Parent Class for your strategies.
Aside from ``algo.run(...)``, all the other methods should be called
from within your strategy via ``self.MethodName(...)``.

For example:

.. code:: python

    # startegy.py

    # record something
    self.record(key=value)

    # send custom text
    self.sms("message text")

    # get instrument object
    instrument = self.get_instrument("SYMBOL")


.. autoclass:: qtpylib.algo.Algo
    :members: run, on_start, on_quote, on_tick, on_bar, on_fill, record, sms, get_instrument, order, cancel_order, get_history
    :member-order: bysource
    :noindex: