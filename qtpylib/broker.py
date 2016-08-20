#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# QTPy-Lib: Quantitative Trading Python Library
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
#

import atexit
import ezibpy
import glob
import hashlib
import logging
import os
import pandas as pd
import pickle
import pymysql
import sys
import tempfile

from datetime import datetime, timedelta

from qtpylib import (
    tools, sms
)

from abc import ABCMeta

class Broker():
    """Broker class initilizer (abstracted, parent class of ``Algo``)

    :Parameters:

        instruments : list
            List of IB contract tuples
        ibclient : int
            IB TWS/GW Port to use (default: 4001)
        ibport : int
            IB TWS/GW Client ID (default: 998)
        ibserver : string
            IB TWS/GW Server hostname (default: localhost)
    """

    __metaclass__ = ABCMeta

    def __init__(self, instruments, ibclient=999, ibport=4001, ibserver="localhost", **kwargs):

        # -----------------------------------
        # detect running strategy
        self.strategy = str(self.__class__).split('.')[-1].split("'")[0]

        # -----------------------------------
        # connect to IB
        self.ibConn = ezibpy.ezIBpy()
        self.ibConn.connect(clientId=int(ibclient), host=ibserver, port=int(ibport))
        self.ibConn.ibCallback = self.ibCallback

        self.ibConn.requestPositionUpdates(subscribe=True)
        self.ibConn.requestAccountUpdates(subscribe=True)

        # -----------------------------------
        # create contracts
        instrument_tuples_dict = {}
        for instrument in instruments:
            try:
                # signgle stock string
                if isinstance(instrument, str):
                    instrument = (instrument, "STK", "SMART", "USD", "", 0.0, "")

                # tuples without strike/right
                elif len(instrument) <= 7:
                    instrument_list = list(instrument)
                    if len(instrument_list) < 3:
                        instrument_list.append("SMART")
                    if len(instrument_list) < 4:
                        instrument_list.append("USD")
                    if len(instrument_list) < 5:
                        instrument_list.append("")
                    if len(instrument_list) < 6:
                        instrument_list.append(0.0)
                    if len(instrument_list) < 7:
                        instrument_list.append("")

                    try: instrument_list[4] = int(instrument_list[4])
                    except: pass

                    instrument_list[5] = 0. if isinstance(instrument_list[5], str) \
                        else float(instrument_list[5])

                    instrument = tuple(instrument_list)

                contractString = self.ibConn.contractString(instrument)
                instrument_tuples_dict[contractString] = instrument
                self.ibConn.createContract(instrument)
            except:
                pass

        self.instruments = instrument_tuples_dict
        self.symbols = list(self.instruments.keys())

        # -----------------------------------
        # easy access to ibconn objects
        self.orderbook = self.ibConn.marketDepthData
        self.account   = self.ibConn.account
        self.positions = self.ibConn.positions
        self.portfolio = self.ibConn.portfolio
        self.contracts = self.ibConn.contracts

        # -----------------------------------
        # track orders & trades
        self.active_trades = {}
        self.trades = []

        # use: self.orders.pending...
        self.orders = tools.make_object(
            by_tickerid = self.ibConn.orders,
            by_symbol = self.ibConn.symbol_orders,
            pending_ttls = {},
            pending = {},
            filled = {},
            active = {},
            history = {},
            nextId = 1,
            recent = {}
        )

        # -----------------------------------
        self.dbcurr = None
        self.dbconn = None

        # -----------------------------------
        # assign default vals if not propogated from algo
        if not hasattr(self, 'backtest'):
            self.backtest = False

        if not hasattr(self, 'sms_numbers'):
            self.sms_numbers = []

        if not hasattr(self, 'trade_log_dir'):
            self.trade_log_dir = None

        if not hasattr(self, 'blotter_name'):
            self.blotter_name = None

        # -----------------------------------
        # load blotter settings
        self.blotter_args = {}
        self.load_blotter_args(self.blotter_name)

        # -----------------------------------
        # do stuff on exit
        atexit.register(self.on_exit)


    # -------------------------------------------
    def load_blotter_args(self, name=None):
        if name is not None:
            self.blotter_name = name

        # find specific name
        if self.blotter_name is not None: # and self.blotter_name != 'auto-detect':
            args_cache_file = tempfile.gettempdir()+"/"+self.blotter_name.lower()+".ezq"
            if not os.path.exists(args_cache_file):
                print("[ERROR] Cannot connect to running Blotter [%s]" % (self.blotter_name))
                sys.exit(0)

        # no name provided - connect to last running
        else:
            blotter_files = sorted(glob.glob(tempfile.gettempdir()+"/*.ezq"), key=os.path.getmtime)
            if len(blotter_files) == 0:
                print("[ERROR] Cannot connect to running Blotter [%s]" % (self.blotter_name))
                sys.exit(0)

            args_cache_file = blotter_files[-1]

        args = pickle.load( open(args_cache_file, "rb" ) )
        args['as_client'] = True

        if args:
            # connect to mysql
            self.dbconn = pymysql.connect(
                host   = str(args['dbhost']),
                port   = int(args['dbport']),
                user   = str(args['dbuser']),
                passwd = str(args['dbpass']),
                db     = str(args['dbname'])
            )
            self.dbcurr = self.dbconn.cursor()

        self.blotter_args = args

    # -------------------------------------------
    def on_exit(self):
        logging.info("Algo stopped...")

        if self.ibConn is not None:
            logging.info("Cancel market data...")
            self.ibConn.cancelMarketData()

            logging.info("Disconnecting...")
            self.ibConn.disconnect()

        logging.info("Disconnecting from MySQL...")
        try:
            self.dbcurr.close()
            self.dbconn.close()
        except:
            pass

    # ---------------------------------------
    # @abstractmethod
    def ibCallback(self, caller, msg, **kwargs):
        if caller == "handleOrders":
            # print("handleOrders" , msg)

            order    = self.ibConn.orders[msg.orderId]

            # print("***********************\n\n", order, "\n\n***********************")
            orderId  = msg.orderId
            symbol   = order["symbol"]

            try:
                try:
                    quantity = self.orders.history[symbol][orderId]['quantity']
                except:
                    quantity = self.orders.history[symbol][order['parentId']]['quantity']
                    # ^^ for child orders auto-created by ezibpy
            except:
                quantity = 1

            # update pending order to the time actually submitted
            if order["status"] in ["OPENED", "SUBMITTED"]:
                if orderId in self.orders.pending_ttls:
                    self._update_pending_order(symbol, orderId, self.orders.pending_ttls[orderId], quantity)

            elif order["status"] == "FILLED":
                self._update_order_history(symbol, orderId, quantity, filled=True)
                self._expire_pending_order(symbol, orderId)
                self._cancel_orphan_orders(symbol, orderId)

                self._register_trade(order)

    # ---------------------------------------
    def _register_trade(self, order):
        """ constructs trade info from order data """
        if order['id'] in self.orders.recent:
            orderId = order['id']
        else:
            orderId = order['parentId']
        # entry / exit?
        symbol     = order["symbol"]
        order_data = self.orders.recent[orderId]
        position   = self.get_positions(symbol)['position']

        if position != 0:
            # entry
            order_data['action']      = "ENTRY"
            order_data['position']    = position
            order_data['entry_time']  = tools.datetime_to_timezone(order['time'])
            order_data['exit_time']   = None
            order_data['entry_order'] = order_data['order_type']
            order_data['entry_price'] = order['avgFillPrice']
            order_data['exit_price']  = 0
            order_data['exit_reason'] = None

        else:
            order_data['action']      = "EXIT"
            order_data['position']    = 0
            order_data['exit_time']   = tools.datetime_to_timezone(order['time'])
            order_data['exit_price']  = order['avgFillPrice']

            # target / stop?
            if order['id'] == order_data['targetOrderId']:
                order_data['exit_reason'] = "TARGET"
            elif order['id'] == order_data['stopOrderId']:
                order_data['exit_reason'] = "STOP"
            else:
                order_data['exit_reason'] = "SIGNAL"

            # remove from collection
            del self.orders.recent[orderId]

        if order_data is None:
            return

        # trade identifier
        tradeId = self.strategy.upper()+'_'+symbol.upper()
        tradeId = hashlib.sha1(tradeId.encode()).hexdigest()

        # existing trade?
        if tradeId not in self.active_trades:
            self.active_trades[tradeId] = {
                "strategy"     : self.strategy,
                "action"       : order_data['action'],
                "quantity"     : abs(order_data['position']),
                "position"     : order_data['position'],
                "symbol"       : order_data["symbol"].split('_')[0],
                "direction"    : order_data['direction'],
                "entry_time"   : None,
                "exit_time"    : None,
                "duration"     : "0s",
                "exit_reason"  : order_data['exit_reason'],
                "order_type"   : order_data['order_type'],
                "market_price" : order_data['price'],
                "target"       : order_data['target'],
                "stop"         : order_data['initial_stop'],
                "entry_price"  : 0,
                "exit_price"   : order_data['exit_price'],
                "realized_pnl" : 0
            }
            if "entry_time" in order_data:
                self.active_trades[tradeId]["entry_time"] = order_data['entry_time']
            if "entry_price" in order_data:
                self.active_trades[tradeId]["entry_price"] = order_data['entry_price']
        else:
            # self.active_trades[tradeId]['direction']   = order_data['direction']
            self.active_trades[tradeId]['action']      = order_data['action']
            self.active_trades[tradeId]['position']    = order_data['position']
            self.active_trades[tradeId]['exit_price']  = order_data['exit_price']
            self.active_trades[tradeId]['exit_reason'] = order_data['exit_reason']
            self.active_trades[tradeId]['exit_time']   = order_data['exit_time']

            # calculate trade duration
            try:
                delta = int((self.active_trades[tradeId]['exit_time']-self.active_trades[tradeId]['entry_time']).total_seconds())
                days, remainder = divmod(delta, 86400)
                hours, remainder = divmod(remainder, 3600)
                minutes, seconds = divmod(remainder, 60)
                duration = ('%sd %sh %sm %ss' % (days, hours, minutes, seconds))
                self.active_trades[tradeId]['duration'] = duration.replace("0d ", "").replace("0h ", "").replace("0m ", "")
            except:
                pass

            trade = self.active_trades[tradeId]
            if trade['entry_price'] > 0 and trade['position'] == 0:
                pnl = trade['exit_price']-trade['entry_price']
                pnl = -pnl if trade['direction'] == "BUY" else pnl
                self.active_trades[tradeId]['realized_pnl'] = pnl

        # print("\n\n-----------------")
        # print(self.active_trades[tradeId])
        # print("-----------------\n\n")

        # get trade
        trade = self.active_trades[tradeId].copy()
        trade['direction'] = trade['direction'].replace("BUY", "LONG").replace("SELL", "SHORT")

        # sms
        sms._send_trade(trade, self.sms_numbers, self.timezone)

        # log
        self.log_trade(trade)

        # remove from active trades and add to trade
        if trade['action'] == "EXIT":
            del self.active_trades[tradeId]
            self.trades.append(trade)

        # return trade
        return trade


    # ---------------------------------------
    def log_trade(self, trade):

        # first trade is an exit?
        if trade['entry_time'] is None:
            return

        # connection established
        if (self.dbconn is not None) & (self.dbcurr is not None):

            sql = """INSERT INTO trades (
                `algo`, `symbol`, `direction`,`quantity`,
                `entry_time`, `exit_time`, `exit_reason`,
                `order_type`, `market_price`, `target`, `stop`,
                `entry_price`, `exit_price`, `realized_pnl`)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE
                    `algo`=%s, `symbol`=%s, `direction`=%s, `quantity`=%s,
                    `entry_time`=%s, `exit_time`=%s, `exit_reason`=%s,
                    `order_type`=%s, `market_price`=%s, `target`=%s, `stop`=%s,
                    `entry_price`=%s, `exit_price`=%s, `realized_pnl`=%s
                """

            try: trade['entry_time'] = trade['entry_time'].strftime("%Y-%m-%d %H:%M:%S.%f")
            except: pass

            try: trade['exit_time']  = trade['exit_time'].strftime("%Y-%m-%d %H:%M:%S.%f")
            except: pass

            # all strings
            for k,v in trade.items():
                if v is not None:
                    trade[k] = str(v)

            self.dbcurr.execute(sql, (
                trade['strategy'], trade['symbol'], trade['direction'], trade['quantity'],
                trade['entry_time'], trade['exit_time'], trade['exit_reason'],
                trade['order_type'], trade['market_price'], trade['target'], trade['stop'],
                trade['entry_price'], trade['exit_price'], trade['realized_pnl'],
                trade['strategy'], trade['symbol'], trade['direction'], trade['quantity'],
                trade['entry_time'], trade['exit_time'], trade['exit_reason'],
                trade['order_type'], trade['market_price'], trade['target'], trade['stop'],
                trade['entry_price'], trade['exit_price'], trade['realized_pnl']
            ))

            # commit
            try:
                self.dbconn.commit()
            except:
                pass


        if self.trade_log_dir:
            self.trade_log_dir = (self.trade_log_dir+'/').replace('//', '/')
            trade_log_path = self.trade_log_dir+self.strategy.lower()+"_"+datetime.now().strftime('%Y%m%d')+".csv"

            trade_df = pd.DataFrame(index=[0], data=trade)[[
                'strategy','symbol','direction','quantity','entry_time','exit_time','exit_reason',
                'order_type','market_price','target','stop','entry_price','exit_price','realized_pnl'
            ]]

            if os.path.exists(trade_log_path):
                trades = pd.read_csv(trade_log_path, header=0)
                trades = trades.append(trade_df, ignore_index=True)
                trades.drop_duplicates(['entry_time', 'symbol', 'strategy'], keep="last", inplace=True)
                trades.to_csv(trade_log_path, header=True, index=False)
            else:
                trade_df.to_csv(trade_log_path, header=True, index=False)


    # ---------------------------------------
    def active_order(self, symbol, order_type="STOP"):
        if symbol in self.orders.history:
            for orderId in self.orders.history[symbol]:
                order = self.orders.history[symbol][orderId]
                if order['order_type'].upper() == order_type.upper():
                    return order
        return None


    # ---------------------------------------
    def _get_locals(self, locals):
        del locals['self']
        return locals

     # ---------------------------------------
    def _create_order(self, symbol, direction, quantity, order_type="", \
        limit_price=0, expiry=0, orderId=0, ticksize=0.01, \
        target=0, initial_stop=0, trail_stop_at=0, trail_stop_by=0):

        # force BUY/SELL (not LONG/SHORT)
        direction = direction.replace("LONG", "BUY").replace("SHORT", "SELL")

        # modify order?
        if order_type.upper() == "MODIFY":
            self.modify_order(symbol, orderId, quantity, limit_price)
            return

        # continue...

        order_type = "MARKET" if limit_price == 0 else "LIMIT"

        # clear expired pending orders
        self._cancel_expired_pending_orders()

        # don't submit order if a pending one is waiting
        if symbol in self.orders.pending:
            # print("--------------------------------------------------")
            # print("pending order")
            # print(self.orders.pending)
            # print("--------------------------------------------------")
            return

        # @TODO - decide on quantity here

        # continue...
        order_quantity = abs(quantity)
        if direction.upper() == "SELL":
            order_quantity = -order_quantity

        contract = self.get_contract(symbol)

        # is bracket order
        bracket = (target > 0) | (initial_stop > 0) | (trail_stop_at > 0) | (trail_stop_by > 0)

        # create & submit order
        if bracket == False:
            # simple order
            order    = self.ibConn.createOrder(order_quantity, limit_price)
            orderId  = self.ibConn.placeOrder(contract, order)
        else:
            # bracket order
            order = self.ibConn.createBracketOrder(contract, order_quantity,
                entry=limit_price, target=target, stop=initial_stop)
            orderId = order["entryOrderId"]

            # triggered trailing stop?
            if (trail_stop_by != None) & (trail_stop_at != None):
                self.ibConn.createTriggerableTrailingStop(symbol, -order_quantity,
                    triggerPrice  = trail_stop_at,
                    trailPercent  = trail_stop_by,
                    # trailAmount   = trail_stop_by,
                    parentId      = order['entryOrderId'],
                    stopOrderId   = order["stopOrderId"],
                    ticksize      = ticksize
                )

            # add all orders to history
            self._update_order_history(symbol=symbol, orderId=order["entryOrderId"],
                quantity=order_quantity, order_type='ENTRY')

            self._update_order_history(symbol=symbol, orderId=order["targetOrderId"],
                quantity=-order_quantity, order_type='TARGET', parentId=order["entryOrderId"])

            self._update_order_history(symbol=symbol, orderId=order["stopOrderId"],
                quantity=-order_quantity, order_type='STOP', parentId=order["entryOrderId"])


        # have original params available for FILL event
        self.orders.recent[orderId] = self._get_locals(locals())
        self.orders.recent[orderId]['targetOrderId'] = 0
        self.orders.recent[orderId]['stopOrderId'] = 0
        if bracket:
            self.orders.recent[orderId]['targetOrderId'] = order["targetOrderId"]
            self.orders.recent[orderId]['stopOrderId'] = order["stopOrderId"]
        # append market price at the time of order
        try: self.orders.recent[orderId]['price'] = self.ticks[-1:]['last'][0]
        except: self.orders.recent[orderId]['price'] = 0

        # add orderId / ttl to (auto-adds to history)
        expiry = expiry*1000 if expiry > 0 else 60000 # 1min
        self._update_pending_order(symbol, orderId, expiry, order_quantity)


    # ---------------------------------------
    def modify_order(self, symbol, orderId, quantity=None, limit_price=None):
        if quantity is None and limit_price is None:
            return

        if symbol in self.orders.history:
            for historyOrderId in self.orders.history[symbol]:
                if historyOrderId == orderId:
                    order = self.orders.history[symbol][orderId]
                    if order['order_type'] == "STOP":
                        # request
                        self.ibConn.modifyStopOrder(orderId, order['parentId'], limit_price, quantity)
                        break
                    # elif order['order_type'] == "LMT" and "parentId" in order:
                    #     order.m_lmtPrice = limit_price
                    #     self.ibConn.placeOrder(self.get_contract(symbol), order, orderId=order['parentId'])
                    else:
                        order.m_lmtPrice = limit_price
                        self.ibConn.placeOrder(self.get_contract(symbol), order, orderId=orderId)
                        break

    # ---------------------------------------
    def _milliseconds_delta(self, delta):
        return delta.days*86400000 + delta.seconds*1000 + delta.microseconds/1000

    # ---------------------------------------
    def _cancel_orphan_orders(self, symbol, orderId):
        """ cancel child orders when parent is gone """
        orders = self.ibConn.orders
        for order in orders:
            order = orders[order]
            if order['parentId'] != orderId:
                self.ibConn.cancelOrder(order['id'])

    # ---------------------------------------
    def _cancel_expired_pending_orders(self):
        """ expires pending orders """
        # use a copy to prevent errors
        pending = self.orders.pending.copy()
        for symbol in pending:
            orderId    = pending[symbol]["orderId"]
            expiration = pending[symbol]["expires"]

            delta = expiration-datetime.now()
            delta = self._milliseconds_delta(delta)

            # cancel order if expired
            if delta < 0:
                self.ibConn.cancelOrder(orderId)
                if orderId in self.orders.pending_ttls:
                    if orderId in self.orders.pending_ttls:
                        del self.orders.pending_ttls[orderId]
                    if symbol in self.orders.pending:
                        if self.orders.pending[symbol]['orderId'] == orderId:
                            del self.orders.pending[symbol]

    # ---------------------------------------------------------
    def _expire_pending_order(self, symbol, orderId):
        self.ibConn.cancelOrder(orderId)

        if orderId in self.orders.pending_ttls:
            del self.orders.pending_ttls[orderId]

        if symbol in self.orders.pending:
            if self.orders.pending[symbol]['orderId'] == orderId:
                del self.orders.pending[symbol]

    # ---------------------------------------------------------
    def _update_pending_order(self, symbol, orderId, expiry, quantity):
        self.orders.pending[symbol] = {
            "orderId": orderId,
            "quantity": quantity,
            # "created": datetime.now(),
            "expires": datetime.now() + timedelta(milliseconds=expiry)
        }

        # ibCallback needs this to update with submittion time
        self.orders.pending_ttls[orderId] = expiry
        self._update_order_history(symbol=symbol, orderId=orderId, quantity=quantity)

    # ---------------------------------------------------------
    def _update_order_history(self, symbol, orderId, quantity, order_type='entry', filled=False, parentId=0):
        if symbol not in self.orders.history:
            self.orders.history[symbol] = {}

        self.orders.history[symbol][orderId] = {
            "orderId": orderId,
            "quantity": quantity,
            "order_type": order_type.upper(),
            "filled": filled,
            "parentId": parentId
        }



    # ---------------------------------------
    # UTILITY FUNCTIONS
    # ---------------------------------------
    def _getsymbol_(self, symbol):
        if not isinstance(symbol, str):
            if isinstance(symbol, dict):
                symbol = symbol['symbol']
            elif isinstance(symbol, pd.DataFrame):
                symbol = symbol[:1]['symbol'].values[0]

        return symbol

    # ---------------------------------------
    def get_contract(self, symbol):
        return self.ibConn.contracts[self.ibConn.tickerId(symbol)]

    # ---------------------------------------
    def get_orders(self, symbol):
        symbol = self._getsymbol_(symbol)

        if symbol in self.orders.by_symbol:
            return self.orders.by_symbol[symbol]

        return {}

    # ---------------------------------------
    def get_orderbook(self, symbol):
        symbol = self._getsymbol_(symbol)

        if symbol in self.positions:
            return self.orderbook[symbol]

        return {
            "bid":0, "bidsize":0,
            "ask":0, "asksize":0
        }

    # ---------------------------------------
    def get_positions(self, symbol):
        symbol = self._getsymbol_(symbol)

        if symbol in self.positions:
            return self.positions[symbol]

        return {
            "symbol": symbol,
            "position": 0,
            "avgCost":  0.0,
            "account":  None
        }

    # ---------------------------------------
    def get_portfolio(self, symbol=None):
        if (symbol is not None):
            symbol = self._getsymbol_(symbol)

            if (symbol in self.positions):
                return self.portfolio[symbol]

        return self.portfolio


    # ---------------------------------------
    def get_pending_orders(self, symbol=None):
        if (symbol is not None):
            symbol = self._getsymbol_(symbol)

        return (symbol in self.orders.pending)

