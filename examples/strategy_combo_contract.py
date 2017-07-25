#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# QTPyLib: Quantitative Trading Python Library
# https://github.com/ranaroussi/qtpylib
#
# Copyright 2016 Ran Aroussi
#
# Licensed under the GNU Lesser General Public License, v3.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.gnu.org/licenses/lgpl-3.0.en.html
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from qtpylib.algo import Algo


class SpreadStrategy(Algo):
    """
    Example: This Strategy buys/sells a spread (combo contract)
    whenever spread > 1.0. Sells on next tick.
    """

    def on_start(self):
        print(self.instruments)

    def on_tick(self, instrument):

        # combo structure is:
        # dict {
        #     "parent": instrument,
        #     "legs": {"symbol": instrument, "symbol": instrument, ...}
        # }

        # get all instruments (legs) in combo contract
        combo = instrument.combo
        # print(combo)

        # wait until we have price in all legs
        for leg in combo['legs'].values():
            if leg.price is None:
                return

        # calculate spread price
        front_price = combo['legs']['ESU2017_FUT'].price
        back_price = combo['legs']['ESZ2017_FUT'].price
        spread = front_price - back_price
        print("Spread >>", spread)

        # spread threshold?
        # if spread < 1:
        #     return

        """
        # combo orders still not woking for some reason :(
        # maybe an issue with ezIBpy?

        if combo['parent'].positions['position']:
            print("In position. Exiting...")
            combo['parent'].exit()
        else:
            if combo['parent'].pending_orders:
                print("Pending order. Waiting...")
            else:
                # random order direction
                print("Not in position. Buying using a market order...")
                combo['parent'].buy(1)
        """


# ===========================================


if __name__ == "__main__":

    # ---------------------------------------
    # 1. initialize strategy
    # ---------------------------------------
    strategy = SpreadStrategy()

    # ---------------------------------------
    # 2. create combo contract using ezIBpy methods
    # ---------------------------------------

    # create contract legs
    front_contract = strategy.ibConn.createFuturesContract(
        "ES", exchange="GLOBEX", expiry=201709)
    back_contract = strategy.ibConn.createFuturesContract(
        "ES", exchange="GLOBEX", expiry=201712)

    # create combo legs
    leg1 = strategy.ibConn.createComboLeg(front_contract, "BUY", ratio=1)
    leg2 = strategy.ibConn.createComboLeg(back_contract, "SELL", ratio=1)

    # add legs to contract
    spread_contract = strategy.ibConn.createComboContract(
        "ES_SPREAD", [leg1, leg2])

    # add all contracts to strategy
    strategy.add_instruments(front_contract, back_contract, spread_contract)
    # ---------------------------------------

    # ---------------------------------------
    # 3. register combo contracts
    # ---------------------------------------
    strategy.register_combo(parent=spread_contract,
                            legs=[front_contract, back_contract])

    # ---------------------------------------
    # 4. run strategy
    # ---------------------------------------
    strategy.run()
