Instrument API
--------------

The Instrument object is passed to the ``on_tick()``,
``on_bar()``, ``on_quote()``, ``on_orderbook()``
and ``on_fill()`` methods in your strategy:

.. code:: python

    # startegy.py
    def on_tick(self, instrument):
        instrument.MethodName(...)

    def on_bar(self, instrument):
        instrument.MethodName(...)

    def on_quote(self, instrument):
        instrument.MethodName(...)

    def on_orderbook(self, instrument):
        instrument.MethodName(...)

    def on_fill(self, instrument, order):
        instrument.MethodName(...)


.. autoclass:: qtpylib.instrument.Instrument
    :members:
    :member-order: bysource
    :noindex: