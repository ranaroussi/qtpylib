Instrument API
--------------

The Instrument object is passed to the ``on_tick(...)``
and ``on_bar(...)`` methods in your strategy:

.. code:: python

    # startegy.py
    def on_tick(self, instrument):
        instrument.MethodName(...)

    def on_bar(self, instrument):
        instrument.MethodName(...)


.. autoclass:: qtpylib.instrument.Instrument
    :members:
    :member-order: bysource
    :noindex: