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

from qtpylib.blotters import BaseBlotter
import time

import multitasking
import signal
import sys

signal.signal(signal.SIGINT, multitasking.killall)
multitasking.set_engine("process")


class Blotter(BaseBlotter):

    @multitasking.task
    def run(self, *args, **kwargs):
        # load data from datastore/csv
        history = "..."

        drip_handler = self._tick_handler if self.resolution[-1] in (
                "S", "K", "V") else self._bar_handler
        self.drip(history, drip_handler)

    def preload_history(self, config=None):
        # split data as "preloading"
        self.preloaded_data = "..."

    def drip(data, handler):
        try:
            for i in range(len(data)):
                handler(data.iloc[i:i + 1])
                time.sleep(.15)

            print("\n\n>>> Backtesting Completed.")

        except (KeyboardInterrupt, SystemExit):
            print("\n\n>>> Interrupted with Ctrl-c...")
            print("(waiting for running tasks to be completed)\n")
            print(".\n.\n.\n")
            sys.exit(1)
