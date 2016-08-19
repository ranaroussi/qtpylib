Instrument API
==============

**Do NOT initilize this class directly!** Instead, you should
initilize it using ``self.get_instrument()`` from within your
strategy.

For example:

.. code:: python

    # startegy.py
    instrument = self.get_instrument(bar)
    instrument.MethodName(...)


.. autoclass:: qtpylib.instrument.Instrument
   :members: