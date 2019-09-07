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

import sys as _sys
# import atexit
import logging as _logging
import json as _json
import zmq as _zmq

import numpy as _np
import pandas as _pd
from qtpylib import tools
from abc import ABCMeta, abstractmethod

import tempfile
import os

import time
import multitasking
import signal
signal.signal(signal.SIGINT, multitasking.killall)


# =============================================
# check min, python version
if _sys.version_info < (3, 4):
    raise SystemError("QTPyLib requires Python version >= 3.4")

# =============================================


class BaseBlotter():

    __metaclass__ = ABCMeta

    def __init__(self, blotter, datastore=None, instruments=None,
                 pubport=55555, subport=55556, **kwargs):

        # settings
        self.name = str(self.__class__).split('.')[-1].split("'")[0]

        # read cached args to detect duplicate blotters
        self.duplicate_run = False
        self.cahced_args = {}
        self.args_cache_file = "%s/%s.qtpylib" % (
            tempfile.gettempdir(), self.name)
        if os.path.exists(self.args_cache_file):
            self.cahced_args = self._read_cached_args()

        # continue setup
        self.logger = tools.createLogger(self.name, _logging.INFO)
        self.blotter = tools.parse_protocol(blotter)

        # datastore
        self.datastore = tools.init_datastore(datastore)
        self.datastore.connect()

        # backtester placeholder
        self.preloaded_data = None

        # publisher socket (broadcasts to algos)
        self.publisher = _zmq.Context().socket(_zmq.PUB)
        self.publisher.bind("tcp://*:%s" % str(pubport))

        # commnicator (communicates with algos)
        self._listen_to_socket(subport)

    # -------------------------------------------
    @multitasking.task
    def _listen_to_socket(self, subport):
        socket = _zmq.Context().socket(_zmq.REP)
        socket.bind("tcp://*:%s" % str(subport))

        while True:
            msg = socket.recv_string()
            socket.send_string('[REPLY] %s' % msg)
            time.sleep(1)

    # -------------------------------------------
    def broadcast(self, kind: str, data: dict) -> None:
        def int64handler(o):
            if isinstance(o, _np.int64):
                try:
                    return _pd.to_datetime(o, unit='ms').strftime('???')
                except Exception:
                    return int(o)
            raise TypeError

        try:
            self.publisher.send_string("%s: %s: %s" % (
                self.name, str(kind), _json.dumps(data, default=int64handler)))
        except Exception:
            pass

    # -------------------------------------------
    @abstractmethod
    def preload_history(self):
        """ used by backtester (simply split the data) """
        pass

    # -------------------------------------------
    @abstractmethod
    def run(self, *args, **kwargs):
        """ placeholder: every blotter needs to implement this! """
        pass



    """
    # -------------------------------------------
    @staticmethod
    def _blotter_file_running():
        try:
            # not sure how this works on windows...
            command = 'pgrep -f ' + sys.argv[0]
            process = subprocess.Popen(
                command, shell=True, stdout=subprocess.PIPE)
            stdout_list = process.communicate()[0].decode('utf-8').split("\n")
            stdout_list = list(filter(None, stdout_list))
            return len(stdout_list) > 0
        except Exception:
            return False

    # -------------------------------------------
    def _check_unique_blotter(self):
        if os.path.exists(self.args_cache_file):
            # temp file found - check if really running
            # or if this file wasn't deleted due to crash
            if not self._blotter_file_running():
                # print("REMOVING OLD TEMP")
                self._remove_cached_args()
            else:
                self.duplicate_run = True
                self.log_blotter.error("Blotter is already running...")
                sys.exit(1)

        self._write_cached_args()

    # -------------------------------------------
    def _remove_cached_args(self):
        if os.path.exists(self.args_cache_file):
            os.remove(self.args_cache_file)

    def _read_cached_args(self):
        if os.path.exists(self.args_cache_file):
            return pickle.load(open(self.args_cache_file, "rb"))
        return {}

    def _write_cached_args(self):
        pickle.dump(self.args, open(self.args_cache_file, "wb"))
        tools.chmod(self.args_cache_file)

    """

