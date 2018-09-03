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

import random

from qtpylib.algo import Algo
from qtpylib import futures


class TestStrategy(Algo):
    """
    Example: This Strategy buys/sells single contract of the
    S&P E-mini Futures (ES) every 10th tick with a +/- 0.5
    tick target/stop using LIMIT order.

    If still in position for next 5 ticks, an exit order is issued.
    """

    count = 0

    # ---------------------------------------
    def on_start(self):
        """ initilize tick counter """
        self.count = 0

    # ---------------------------------------
    def on_quote(self, instrument):
        # quote = instrument.get_quote()
        # ^^ quote data available via get_quote()
        pass

    # ---------------------------------------
    def on_orderbook(self, instrument):
        pass

    # ---------------------------------------
    def on_fill(self, instrument, order):
        pass

    # ---------------------------------------
    def on_tick(self, instrument):

        # increase counter and do nothing if nor 10th tick
        self.count += 1

        if self.count % 10 != 0:
            return

        # continue ...

        # get last tick dict
        tick = instrument.get_ticks(lookback=1, as_dict=True)

        if instrument.positions['position']:
            print(instrument.symbol, "still in position. Exiting...")
            instrument.exit()
        else:
            if instrument.pending_orders:
                print(instrument.symbol, "has a pending order. Wait...")
            else:
                # random order direction
                direction = random.choice(["BUY", "SELL"])
                print(instrument.symbol,
                      'not in position. Sending a bracket ', direction, 'order...')

                if direction == "BUY":
                    target = tick['last'] + 0.5
                    stoploss = tick['last'] - 0.5
                else:
                    target = tick['last'] - 0.5
                    stoploss = tick['last'] + 0.5

                instrument.order(direction, 1,
                                 limit_price=tick['last'],
                                 target=target,
                                 initial_stop=stoploss,
                                 trail_stop_at=0,
                                 trail_stop_by=0,
                                 expiry=5
                                 )

                # record action
                self.record(take_action=1)

    # ---------------------------------------
    def on_bar(self, instrument):
        # nothing exiting here...
        bar = instrument.get_bars(lookback=1, as_dict=True)
        print("BAR:", bar)



# ===========================================
if __name__ == "__main__":
    # get most active ES contract to trade
    ACTIVE_MONTH = futures.get_active_contract("ES")
    print("Active month for ES is:", ACTIVE_MONTH)

    strategy = TestStrategy(
        instruments=[("ES", "FUT", "GLOBEX", "USD", ACTIVE_MONTH, 0.0, "")],
        resolution="1T",
        tick_window=10,
        bar_window=10
    )
    strategy.run()
