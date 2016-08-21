Getting Market Data
===================

Market Data retrieval is done by a piece of software called a
**Blotter**. A Blotter connects to the broker (in QTPy-Lib's case,
Interactive Brokers via TWS/IB), handles incoming market data
and passes it to the algo for processing.

Blotters optionally (but usually) also take care of storing the market
data in a Database for later analysis, back-testing new strategies, etc.

In QTPy-Lib's case, the Blotter handle all of the above, while your
algorithms subscribe to the Blotter's updates via pub/sub
mechanism using ZeroMQ - a blazing fast Message Queue.

.. note::
    QTPy-Lib was designed with a **"One Blotter To Rule Them All"**
    design in mind. All your algorithms can listen to a single
    Blotter running in the background without a problem and without
    consuming any unnessecery system resources.
    Simply put: **do not run multiple Blotters unless you have
    a very specific reason to do so.**


-----

Creating the Database
---------------------

The first thing you need to do is to create the MySQL database
where your Blotter will store tick and minute data for later use.

Once you've created the database, note its name for the next step.
**The Blotter will automatically create the required database tables
when it runs for the first time.**

-----

Writing your Blotter
--------------------

To get started writing your Blotter, you'll need to create
a Blotter object sub-class and name it.

Then, inililize your Blotter by passing your MySQL credentials
and TWS/IBGW port and run it.

.. code:: python

    # blotter.py
    from qtpylib.blotter import Blotter

    class MainBlotter(Blotter):
        pass # we just need the name

    if __name__ == "__main__":
        blotter = MainBlotter(
            dbhost   = "localhost",
            dbname   = "qtpy",
            dbuser   = "master",
            dbpass   = "blaster",
            ibport   = 4001, # 7496/7497 = TWS, 4001 = IBGateway
        )

        blotter.run()

-----

Running your Blotter
--------------------

With IB TWS/GW running, run the Blotter from the command line:

.. code:: bash

    $ python blotter.py


Initilizing via CLI
~~~~~~~~~~~~~~~~~~~

You can also override the initilized paramters (or ommit this
part of the code altogether) and pass runtime parameters
using the command line.

In this case, your code would look something like this:

.. code:: python

    # blotter.py
    from qtpylib.blotter import Blotter

    class MainBlotter(Blotter):
        pass # we just need the name

    if __name__ == "__main__":
        blotter = MainBlotter()
        blotter.run()

Then, run the Blotter by passing the parameters via the command line:

.. code:: bash

    $ python blotter.py [--dbport] [--dbname] [--dbuser] [--dbpass] [--ibport] [...]


Available Arguments
~~~~~~~~~~~~~~~~~~~

Below are all the parameters that can either be set via the ``Blotter()`` initilizer
or via CLI:

- ``--symbols`` CSV database of IB contracts for market data fetching (default: ``./symbols.csv``)
- ``--ibport`` TWS/IBGW Port to use (default: ``4001``)
- ``--ibclient`` TWS/IBGW Client ID (default: ``999``)
- ``--ibserver`` IB TWS/GW Server hostname (default: ``localhost``)
- ``--zmqport`` ØMQ Port to use (default: ``12345``)
- ``--dbhost`` MySQL server hostname (default: ``localhost``)
- ``--dbport`` MySQL server port (default: ``3306``)
- ``--dbname`` MySQL server database (default: ``qtpy``)
- ``--dbuser`` MySQL server username (default: ``root``)
- ``--dbpass`` MySQL server password (default: ``None``)
- ``--dbskip`` [flag] Skip MySQL logging of market data (default: ``False``)

-----

Instruments CSV
---------------

Once your Blotter runs for the first time, you'll notice that a new
file named ``symbols.csv`` has been created in the same directory
as your Blotter.

This fill will store all the instruments that algos connecting to this
Blotter will request data for. Your blotter will keep logging market
data for these instruments even when you stop your algos so you have
continious market data stored in your database for future research
and backtesting (expired product will be deleted automatically from
this file).

You can, of course, add or delete unwanted instruments from the
CSV file manually at any time -- without stopping your Blotter.

**Eample a populated** ``symbols.csv`` **file:**

.. code::

    symbol,sec_type,exchange,currency,expiry,strike,opt_type
    AAPL,STK,SMART,USD,,0.0,
    ES,FUT,GLOBEX,USD,201609,0.0,
    NFFX,OPT,SMART,USD,20160819,98.50,PUT


This file's structure is better understood when looked at as a table:

======  ========  ========  ========  ========  ====== ========
symbol  sec_type  exchange  currency  expiry    strike opt_type
======  ========  ========  ========  ========  ====== ========
AAPL    STK       SMART     USD       ""        0.0    ""
ES      FUT       GLOBEX    USD       201609    0.0    ""
NFFX    OPT       SMART     USD       20160819  98.50  PUT
======  ========  ========  ========  ========  ====== ========


-----

With your Blotter running, its time to write your first Algo...
