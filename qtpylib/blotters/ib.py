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
from ezibpy import ezIBpy
import time


class Blotter(BaseBlotter):

    def run(self, *args, **kwargs):

        clientId = int(kwargs["clientId"]) if "clientId" in kwargs else 999

        self.ibConn = ezIBpy()
        self.ibConn.ibCallback = self.ibCallback

        while not self.ibConn.connected:
            self.ibConn.connect(
                clientId=int(clientId),
                port=int(self.blotter["port"]),
                host=str(self.blotter["server"]),
                account=self.blotter["endpoint"])

            time.sleep(1)
            if not self.ibConn.connected:
                print('*', end="", flush=True)

        self.logger.info("Connection established...")

    def ibCallback(self, caller, msg, **kwargs):

        # on event:
        # self.broadcast('kind', 'data')
        # self.datastore.save('kind', 'data')

        pass
