#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# QTPyLib: Quantitative Trading Python Library
# https://github.com/ranaroussi/qtpylib
#
# Copyright 2016-2018 Ran Aroussi
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

from qtpylib.algo import Algo
from qtpylib.pipeline import Ticker  # , Universe


class TestStrategy(Algo):

    # ---------------------------------------
    def on_start(self):
        """ initilize tick counter """
        self.count = 0

    # ---------------------------------------

    def on_bar(self, bars):

        gap = bars["open"] > bars["close"].shift(1)
        longma = bars["close"].rolling(50).mean()
        shortma = bars["close"].rolling(10).mean()

        signals = gap & shortma > longma

        positions = self.broker.get_positions()
        signals == signals[signals != positions]

        # self.record(signals, *kwargs)

        qty = self.broker.allocate(signals, max_funds=1e5)
        self.broker.buy(qty)

    # ---------------------------------------

    def on_complete(self, returns, trades):
        """ similar to quantopian's analyze """
        pass


# ===========================================

if __name__ == "__main__":

    strategy = TestStrategy(
        config="algo.toml",
        # instruments=Universe.Dow30()
        instruments=[
            # Ticker(<name>, <broker identifier>, <blotter identifier>):
            Ticker("aapl", "AAPL.STK", "AAPL@NASDAQ"),
            Ticker("tsla", "TSLA.STK", "TSLA@NASDAQ"),
        ]
    )

    # backtest
    strategy.backtest(None, None, None, data="csv://path/to/csv_directory")

    # live
    # strategy.run()

