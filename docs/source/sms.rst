SMS Notification
================

QTPyLib supports both automatic trade notifications via SMS
and  custom messages (for example, when you want to SMS yourself
signals without entering a trade).

To specify the recipients, add the ``--sms`` flag when running
your algo from the command line:

.. code:: bash

    $ python strategy.py --sms +15551230987 +447781123456 ...

Now, whenever your algo generates a trade or when you send a custom SMS,
these recipients will receive the notification to their phone.

.. note::
    To enable this functionality, you need to have an account with either
    `Nexmo <https://www.nexmo.com/>`_ or `Twilio <https://www.twilio.com/>`_
    and set an SMS Provider for your algo (refer to the
    `SMS Service Provider Setup <#id1>`_
    section below).


Trade Notifications
-------------------

Trades notifications are **enabled by default** and will be sent
whenever your algo makes a trade, as long as you specified recipients
when running the algo.

Trade notifications look like this (followed are made up prices):

.. code::

    11:37:21 UTC
    BOT ▲ 2x ESU2016 @ 2177.0 MKT
    TP 2178.25 / SL 2174.75

    ----

    11:39:29 UTC
    SLD ▼ 2x ESU2016 @ 2178.25 TGT
    PL +1.25 (2m 8s)

    ----

    12:47:29 UTC
    SLD ▼ 2x ESU2016 @ 2174.50 STP
    PL -2.50 (1h 10m 8s)



Custom Notifications
--------------------

Aside from automatic trade notification, you have your algo
send custom messages (for example, when you want to SMS yourself
signals without entering a trade).

To do this, add you need to import the SMS module and add
this code to your algo:

.. code:: python

    self.sms("Look ma, custom text msg...")



SMS Service Provider Setup
--------------------------

To enable this functionality, you need to have an account with either
`Nexmo <https://www.nexmo.com/>`_ or `Twilio <https://www.twilio.com/>`_.

Then, simply create a file named ``sms.ini`` in the same directory as
your ``strategy.py`` file with the following structure:

SMS Using Nexmo
~~~~~~~~~~~~~~~

.. code:: ini

    [nexmo]
    key    = API_KEY
    secret = SECRET_KEY
    from   = FROM_NUMBER (OPTIONAL)


SMS Using Twilio
~~~~~~~~~~~~~~~~

.. code:: ini

    [twilio]
    sid   = ACCOUNT_SID
    token = AUTH_TOKEN
    from  = FROM_NUMBER

.. note:: If your ``sms.ini`` file contains both services, QTPyLib will use the first one listed.
