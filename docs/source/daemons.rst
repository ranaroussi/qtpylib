Run as a Linux Service
======================

In many cases, it may be useful to run your code as a system service
(aka "daemon"), so you can start/stop it using a Cron job, monitor
it using Monit, etc. The following is a quick guide on how to turn
any Python script into a system service on Linux and Unix machines.


The first step is to create your Python script (for this example
we'll use ``blotter.py``).


Create a ``systemd`` Service File
---------------------------------

The next step is to create a ``systemd`` service file to daemonize ``blotter.py``.

From the command line, type:

.. code:: bash

    $ sudo nano /lib/systemd/system/qtpylib-blotter.service


...and add in the following:

.. code:: bash

    [Unit]
    Description=QTPyLib Blotter
    After=multi-user.target

    [Service]
    Type=idle
    ExecStart=/PATH/TO/PYTHON /PATH/TO/blotter.py >/dev/null 2>&1

    [Install]
    WantedBy=multi-user.target

In order to store the Blotter's output in a log file, change the ``ExecStart`` line to:

.. code:: bash

    ExecStart=/path/to/python /path/to/blotter.py > /path/to/blotter.log 2>&1


.. note::
    In most cases the Python executable is found under ``/usr/bin/python``,
    but it can be located elsewhere (for example: ``/home/user/anaconda3/bin/python``).
    You can run ``which python`` to get the path to the System's default Python executable.

Next, change the permission on that file to **644**:

.. code:: bash

    $ sudo chmod 644 /lib/systemd/system/qtpylib-blotter.service


Enable The Service using ``systemctl``
--------------------------------------

Now the system file has been defined, we need to reload ``systemctl``:

.. code:: bash

    $ sudo systemctl daemon-reload
    $ sudo systemctl enable qtpylib-blotter.service


Start/Stop Your Service
-----------------------

**Start the service**

.. code:: bash

    $ sudo service qtpylib-blotter start

**Stop the service**

.. code:: bash

    $ sudo service qtpylib-blotter stop

**Check the service's status**

.. code:: bash

    $ sudo service qtpylib-blotter status


You shoud see something like this:

.. code:: bash

    sudo service qtpylib-blotter status
    ● qtpylib-blotter.service - QTPyLib Blotter
       Loaded: loaded (/lib/systemd/system/qtpylib-blotter.service; enabled; vendor preset: enabled)
       Active: active (running) since Tue 2016-08-22 07:09:06 UTC; 12s ago
     Main PID: 26737 (python)
       CGroup: /system.slice/qtpylib-blotter.service
               └─26737 /usr/bin/python /home/user/blotter.py


