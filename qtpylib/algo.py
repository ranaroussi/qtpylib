#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# QTPyLib: Quantitative Trading Python Library
# https://github.com/ranaroussi/qtpylib
#
# Copyright 2016-2019 Ran Aroussi
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import argparse
import inspect
import sys
import logging
import os

from datetime import datetime
from abc import ABCMeta, abstractmethod

import pandas as pd
from numpy import nan

from qtpylib.broker import Broker
from qtpylib.workflow import validate_columns as validate_csv_columns
from qtpylib.blotter import prepare_history
from qtpylib import (
    tools, sms, asynctools
)

import json
import time
import zmq as _zmq
import toml as _toml

import multitasking
import signal
signal.signal(signal.SIGINT, multitasking.killall)

try:
    from pathlib import Path
    Path().expanduser()
except (ImportError, AttributeError):
    from pathlib2 import Path

# =============================================
# check min, python version
if sys.version_info < (3, 4):
    raise SystemError("QTPyLib requires Python version >= 3.4")

# =============================================
# Configure logging
tools.createLogger(__name__)

# =============================================

"""
class MyAlgo(Algo):
    pass

strategy = MyAlgo(
    config="algo.toml",
    instruments = [
        ticker("AAPL", ("AAPL", "STK", "SMART", "USD", "", 0.0, ""), "AAPL@NASDAQ")
    ]

# backtest
strategy.backtest(None, None, None,
                  data="csv://path/to/csv_directory")

# live
strategy.run()
"""

# =============================================


class Ticker:
    def __init__(self, name, broker=None, blotter=None):
        self.name = name
        self.broker = broker
        self.blotter = blotter if blotter else broker

    def __repr__(self):
        return f'Ticker({self.name})'

# =============================================


class Algo:

    __metaclass__ = ABCMeta

    # -----------------------------------

    def __init__(self, instruments, config=None,
                 backtest=False, start=None, end=None,
                 data=None, output=None, sms_numbers=None):

        self.name = str(self.__class__).split('.')[-1].split("'")[0]
        self.instruments = instruments

        if sms_numbers:
            sms_numbers = sms_numbers if isinstance(
                sms_numbers, list) else [sms_numbers]

        # init config
        self.config = {
            "livemode": False,
            "schedule": None,
            "timezone": "UTC",
            "backtest": {
                "cash": 1e6,
                "commission": {"type": "percent", "value": 0.001},
                "slippage": {"type": "decimal", "value": 0.02},
                "data": "datastore",
                "start": None,
                "end": None,
                "output": None,
            },
            "sms": {"provider": None, "numbers": sms_numbers},
            "events": {"bars": "1T", "tick": 0, "book": False},
            "history": {"tick": 1, "bars": 60, "preload": False},
            "services": {"datastore": None, "blotter": None, "broker": None}
        }

        if config and Path(config).exists():
            self.config = _combine_config(self.config, _toml.load(config))

        if self.config["backtest"]["data"] == "datastore":
            self.config["backtest"]["data"] = self.config[
                "services"]["datastore"]

        self.blotter = None
        # self.record_ts = None
        # if self.record_output:
        #     self.recorder = tools.Recorder()

    # -----------------------------------

    @abstractmethod
    def on_start(self):
        """
        Invoked once when algo starts. Used for when the strategy
        needs to initialize parameters upon starting.
        """
        pass

    # ---------------------------------------
    @abstractmethod
    def on_quote(self):
        """
        Invoked on every quote captured.
        This is where you'll write your strategy logic for quote events.
        """
        pass

    # ---------------------------------------
    @abstractmethod
    def on_tick(self):
        """
        Invoked on every tick captured.
        This is where you'll write your strategy logic for tick events.
        """
        pass

    # ---------------------------------------
    @abstractmethod
    def on_bar(self):
        """
        Invoked on every tick captured.
        This is where you'll write your strategy logic for tick events.

        """
        pass

    # ---------------------------------------
    @abstractmethod
    def on_orderbook(self):
        """
        Invoked on every change to the orderbook.
        This is where you'll write your strategy logic for orderbook events.
        """
        pass

    # ---------------------------------------
    @abstractmethod
    def on_fill(self, order):
        """
        Invoked on every order fill.
        This is where you'll write your strategy logic for fill events.

        :Parameters:
            order : object
                Filled order data
        """
        pass

    # -----------------------------------

    def backtest(self, start, end=None, data=None):
        """
        data = "datastore"
        data = "pystore://path/to/directory"
        data = "mysql://path/to/directory"
        data = "csv://path/to/directory"
        data = "hd5://path/to/directory"
        data = "pkl://path/to/directory"
        """
        if data != "datastore":
            self.config["backtest"]["data"] = data

        self.config["backtest"]["start"] = start
        self.config["backtest"]["end"] = end

        self.config["livemode"] = False
        self._start()

    def run(self, output=None):
        self.config["livemode"] = True
        self._start()

    # -----------------------------------

    @multitasking.task
    def _subscribe_to_blotter(self):
        # load runtime/default data
        # symbols = list(self.instruments.keys())

        # connect to zeromq self.socket
        socket = _zmq.Context().socket(_zmq.SUB)
        socket.setsockopt_string(_zmq.SUBSCRIBE, "")
        socket.connect('tcp://127.0.0.1:' + str(self.args['zmqport']))

        try:
            while True:
                message = socket.recv_string()
                print(message)
                # if self.args["zmqtopic"] in message:

        except (KeyboardInterrupt, SystemExit):
            print("\n\n>>> Interrupted with Ctrl-c...")
            print("(waiting for running tasks to be completed)\n")
            print(".\n.\n.\n")
            sys.exit(1)

    # -----------------------------------

    def _start(self):
        # init datastore
        self.datastore = self.init_datastore(
            self.config["services"]["datastore"])
        self.datastore.connect()

        # init broker
        if self.config["livemode"]:
            self.broker = self.init_broker(self.config["services"]["broker"])
            self.broker.connect()

        # init backtester
        if not self.config["livemode"]:
            self.blotter_port = 1974
            Blotter = tools.dynamic_import('blotters.backtest', 'Blotter')
            self.blotter = Blotter(self.config["backtest"]["data"],
                                   instruments=self.instruments,
                                   zmqport=self.blotter_port)

            if self.config["history"]["preload"]:
                self.blotter.preload_history(self.config["history"])
                self.data = self.blotter.preloaded_data

        else:
            blotter = tools.parse_protocol(self.config["services"]["blotter"])
            self.blotter_port = blotter["port"]

            if self.config["history"]["preload"]:
                # TODO: request history using zmq
                while self.data is None:
                    time.sleep(1)

        # initialize listener
        self._subscribe_to_blotter()

        # tell backtester to start sending data
        # must be multi-processing method
        if not self.config["livemode"]:
            self.blotter.run()

        print(json.dumps(self.config, indent=4, sort_keys=True))


# =============================================

def _combine_config(defaults, user):
    config = dict(defaults)

    for key in user:
        # not in defaults / is none
        if key not in config or config[key] is None:
            config[key] = user[key]

        # override defaults
        else:
            if type(user[key]) != type(config[key]):
                raise ValueError("The setting `%s` must be of type %s" % (
                    key, type(config[key])))
            else:
                if isinstance(user[key], dict):
                    config[key] = _combine_config(config[key], user[key])
                else:
                    config[key] = user[key]
    return config
