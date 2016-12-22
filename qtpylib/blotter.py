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
#

import argparse
import atexit
import json
import logging
import os
import pandas as pd
import pickle
import pymysql
import subprocess
import sys
import tempfile
import time
import zmq
import glob

from numpy import (
    isnan as npisnan,
    nan as npnan
)

from datetime import datetime
from dateutil.parser import parse as parse_date

from ezibpy import (
    ezIBpy, dataTypes as ibDataTypes
)

from qtpylib import (
    tools, asynctools, path, futures, __version__
)

from abc import ABCMeta

# =============================================
# Configure logging
tools.createLogger(__name__, logging.INFO)

# Disable ezIBpy logging (Blotter handles errors itself)
logging.getLogger('ezibpy').setLevel(logging.CRITICAL)
# =============================================

cash_ticks = {}

class Blotter():
    """Broker class initilizer

    :Optional:

        name : string
            name of the blotter (used by other modules)
        symbols : str
            IB contracts CSV database (default: ./symbols.csv)
        ibport : int
            TWS/GW Port to use (default: 4001)
        ibclient : int
            TWS/GW Client ID (default: 999)
        ibserver : str
            IB TWS/GW Server hostname (default: localhost)
        zmqport : str
            ZeroMQ Port to use (default: 12345)
        zmqtopic : str
            ZeroMQ string to use (default: _qtpylib_BLOTTERNAME_)
        orderbook : str
            Get Order Book (Market Depth) data (default: False)
        dbhost : str
            MySQL server hostname (default: localhost)
        dbport : str
            MySQL server port (default: 3306)
        dbname : str
            MySQL server database (default: qpy)
        dbuser : str
            MySQL server username (default: root)
        dbpass : str
            MySQL server password (default: none)
        dbskip : str
            Skip MySQL logging (default: False)
    """

    __metaclass__ = ABCMeta

    def __init__(self, name=None, symbols="symbols.csv",
        ibport=4001, ibclient=999, ibserver="localhost",
        dbhost="localhost", dbport="3306", dbname="qtpy",
        dbuser="root", dbpass="", dbskip=False, orderbook=False,
        zmqport="12345", zmqtopic=None, **kwargs):

        # whats my name?
        self.name = str(self.__class__).split('.')[-1].split("'")[0].lower()
        if name is not None:
            self.name = name

        # initilize class logger
        self.log_blotter = logging.getLogger(__name__)

        # do not act on first tick (timezone is incorrect)
        self.first_tick = True

        self._bars = pd.DataFrame(columns=['open','high','low','close','volume'])
        self._bars.index.names = ['datetime']
        self._bars.index = pd.to_datetime(self._bars.index, utc=True)
        # self._bars.index = self._bars.index.tz_convert(settings['timezone'])
        self._bars = { "~": self._bars }

        self._raw_bars = pd.DataFrame(columns=['last', 'volume'])
        self._raw_bars.index.names = ['datetime']
        self._raw_bars.index = pd.to_datetime(self._raw_bars.index, utc=True)
        # self._raw_bars.index = self._raw_bars.index.tz_convert(settings['timezone'])
        self._raw_bars = { "~": self._raw_bars }

        # global objects
        self.dbcurr  = None
        self.dbconn  = None
        self.context = None
        self.socket  = None
        self.ibConn  = None

        self.symbol_ids = {} # cache
        self.cash_ticks = cash_ticks # outside cache
        self.rtvolume   = set() # has RTVOLUME?

        # -------------------------------
        # work default values
        # -------------------------------
        if zmqtopic is None:
            zmqtopic = "_qtpylib_"+str(self.name.lower())+"_"

        # if no path given for symbols' csv, use same dir
        if symbols == "symbols.csv":
            symbols = path['caller']+'/'+symbols
        # -------------------------------

        # override args with any (non-default) command-line args
        self.args = {arg: val for arg, val in locals().items() if arg not in ('__class__', 'self', 'kwargs')}
        self.args.update(kwargs)
        self.args.update(self.load_cli_args())

        # read cached args to detect duplicate blotters
        self.duplicate_run   = False
        self.cahced_args     = {}
        self.args_cache_file = tempfile.gettempdir()+"/"+self.name+".qtpylib"
        if os.path.exists(self.args_cache_file):
            self.cahced_args = self._read_cached_args()

        # don't display connection errors on ctrl+c
        self.quitting = False

        # do stuff on exit
        atexit.register(self._on_exit)

        # track historical data download status
        self.backfilled = False
        self.backfilled_symbols = []
        self.backfill_resolution = "1 min"

    # -------------------------------------------
    def _on_exit(self, terminate=True):
        if "as_client" in self.args:
            return

        self.log_blotter.info("Blotter stopped...")

        if self.ibConn is not None:
            self.log_blotter.info("Cancel market data...")
            self.ibConn.cancelMarketData()

            self.log_blotter.info("Disconnecting...")
            self.ibConn.disconnect()

        if not self.duplicate_run:
            self.log_blotter.info("Deleting runtime args...")
            self._remove_cached_args()

        self.log_blotter.info("Disconnecting from MySQL...")
        try:
            self.dbcurr.close()
            self.dbconn.close()
        except:
            pass

        if terminate:
            os._exit(0)

    # -------------------------------------------
    def _detect_running_blotter(self, name):
        return name

    # -------------------------------------------
    def _blotter_file_running(self):
        try:
            # not sure how this works on windows...
            command = 'pgrep -f '+ sys.argv[0]
            process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
            stdout_list = process.communicate()[0].decode('utf-8').split("\n")
            stdout_list = list(filter(None, stdout_list))
            return len(stdout_list) > 0
        except:
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
            return pickle.load( open(self.args_cache_file, "rb" ) )
        return {}

    def _write_cached_args(self):
        pickle.dump(self.args, open(self.args_cache_file, "wb"))
        tools.chmod(self.args_cache_file)

    # -------------------------------------------
    def load_cli_args(self):
        parser = argparse.ArgumentParser(description='QTPyLib Blotter',
            formatter_class=argparse.ArgumentDefaultsHelpFormatter)

        parser.add_argument('--symbols', default=self.args['symbols'],
            help='IB contracts CSV database', required=False)
        parser.add_argument('--ibport', default=self.args['ibport'],
            help='TWS/GW Port to use', required=False)
        parser.add_argument('--ibclient', default=self.args['ibclient'],
            help='TWS/GW Client ID', required=False)
        parser.add_argument('--ibserver', default=self.args['ibserver'],
            help='IB TWS/GW Server hostname', required=False)
        parser.add_argument('--zmqport', default=self.args['zmqport'],
            help='ZeroMQ Port to use', required=False)

        parser.add_argument('--orderbook', action='store_true',
            help='Get Order Book (Market Depth) data', required=False)

        parser.add_argument('--dbhost', default=self.args['dbhost'],
            help='MySQL server hostname', required=False)
        parser.add_argument('--dbport', default=self.args['dbport'],
            help='MySQL server port', required=False)
        parser.add_argument('--dbname', default=self.args['dbname'],
            help='MySQL server database', required=False)
        parser.add_argument('--dbuser', default=self.args['dbuser'],
            help='MySQL server username', required=False)
        parser.add_argument('--dbpass', default=self.args['dbpass'],
            help='MySQL server password', required=False)
        parser.add_argument('--dbskip', default=self.args['dbskip'], action='store_true',
            help='Skip MySQL logging (flag)', required=False)

        # only return non-default cmd line args
        # (meaning only those actually given)
        cmd_args, unknown = parser.parse_known_args()
        args = {arg: val for arg, val in vars(cmd_args).items() if val != parser.get_default(arg)}
        return args

    # -------------------------------------------
    def ibCallback(self, caller, msg, **kwargs):

        if caller == "handleConnectionClosed":
            self.log_blotter.info("Lost conncetion to Interactive Brokers...")
            self._on_exit(terminate=False)
            self.run()

        elif caller == "handleHistoricalData":
            self.on_ohlc_received(msg, kwargs)

        elif caller == "handleTickString":
            self.on_tick_string_received(msg.tickerId, kwargs)

        elif caller == "handleTickPrice" or caller == "handleTickSize":
            self.on_quote_received(msg.tickerId)

        elif caller in "handleTickOptionComputation":
            self.on_option_computation_received(msg.tickerId)

        elif caller == "handleMarketDepth":
            self.on_orderbook_received(msg.tickerId)

        elif caller == "handleError":
            # don't display connection errors on ctrl+c
            if self.quitting and \
                msg.errorCode in ibDataTypes["DISCONNECT_ERROR_CODES"]:
                return

            # https://www.interactivebrokers.com/en/software/api/apiguide/tables/api_message_codes.htm
            if 1100 <= msg.errorCode or 0 < 2200: # errorCode can be None...
                self.log_blotter.warning('[IB #{}] {}'.format(msg.errorCode, msg.errorMsg))
            elif msg.errorCode not in (502, 504): # 502, 504 = connection error
                self.log_blotter.error('[IB #{}] {}'.format(msg.errorCode, msg.errorMsg))


    # -------------------------------------------
    def on_ohlc_received(self, msg, kwargs):
        symbol = self.ibConn.tickerSymbol(msg.reqId)

        if kwargs["completed"] == True:
            self.backfilled_symbols.append(symbol)
            tickers = set({v: k for k, v in self.ibConn.tickerIds.items() if v.upper() != "SYMBOL"}.keys())
            if tickers == set(self.backfilled_symbols):
                self.backfilled = True
                print(".")

            try: self.ibConn.cancelHistoricalData(self.ibConn.contracts[msg.reqId]);
            except: pass

        else:
            data = {
                "symbol":       symbol,
                "symbol_group": tools.gen_symbol_group(symbol),
                "asset_class":  tools.gen_asset_class(symbol),
                "timestamp":    tools.datetime_to_timezone(
                    datetime.fromtimestamp(int(msg.date)), tz="UTC").strftime("%Y-%m-%d %H:%M:%S"),
            }

            # incmoing second data
            if "sec" in self.backfill_resolution:
                data["last"]     = tools.to_decimal(msg.close)
                data["lastsize"] = int(msg.volume) # msg.count?
                data["bid"]      = 0
                data["bidsize"]  = 0
                data["ask"]      = 0
                data["asksize"]  = 0
                data["kind"]     = "TICK"
            else:
                data["open"]   = tools.to_decimal(msg.open)
                data["high"]   = tools.to_decimal(msg.high)
                data["low"]    = tools.to_decimal(msg.low)
                data["close"]  = tools.to_decimal(msg.close)
                data["volume"] = int(msg.volume)
                data["kind"]   = "BAR"

            # print(data)

            # store in db
            self.log2db(data, data["kind"])

    # -------------------------------------------
    @asynctools.multitasking.task
    def on_tick_string_received(self, tickerId, kwargs):

        # kwargs is empty
        if not kwargs:
            return

        data = None
        symbol = self.ibConn.tickerSymbol(tickerId)

        # for instruments that receive RTVOLUME events
        if "tick" in kwargs:
            self.rtvolume.add(symbol)
            data = {
                # available data from ib
                "symbol":       symbol,
                "symbol_group": tools.gen_symbol_group(symbol), # ES_F, ...
                "asset_class":  tools.gen_asset_class(symbol),
                "timestamp":    kwargs['tick']['time'],
                "last":         tools.to_decimal(kwargs['tick']['last']),
                "lastsize":     int(kwargs['tick']['size']),
                "bid":          tools.to_decimal(kwargs['tick']['bid']),
                "ask":          tools.to_decimal(kwargs['tick']['ask']),
                "bidsize":      int(kwargs['tick']['bidsize']),
                "asksize":      int(kwargs['tick']['asksize']),
                # "wap":          kwargs['tick']['wap'],
            }

        # for instruments that DOESN'T receive RTVOLUME events (exclude options)
        elif symbol not in self.rtvolume and \
            self.ibConn.contracts[tickerId].m_secType not in ("OPT", "FOP"):

            tick = self.ibConn.marketData[tickerId]

            if len(tick) > 0 and tick['last'].values[-1] > 0 < tick['lastsize'].values[-1]:
                data = {
                    # available data from ib
                    "symbol":       symbol,
                    "symbol_group": tools.gen_symbol_group(symbol), # ES_F, ...
                    "asset_class":  tools.gen_asset_class(symbol),
                    "timestamp":    tick.index.values[-1],
                    "last":         tools.to_decimal(tick['last'].values[-1]),
                    "lastsize":     int(tick['lastsize'].values[-1]),
                    "bid":          tools.to_decimal(tick['bid'].values[-1]),
                    "ask":          tools.to_decimal(tick['ask'].values[-1]),
                    "bidsize":      int(tick['bidsize'].values[-1]),
                    "asksize":      int(tick['asksize'].values[-1]),
                    # "wap":          kwargs['tick']['wap'],
                }

        # proceed if data exists
        if data is not None:
            # cache last tick
            if symbol in self.cash_ticks.keys():
                if data == self.cash_ticks[symbol]:
                    return

            self.cash_ticks[symbol] = data

            # add options fields
            data = tools.force_options_columns(data)

            # print('.', end="", flush=True)
            self.on_tick_received(data)

    # -------------------------------------------
    @asynctools.multitasking.task
    def on_quote_received(self, tickerId):
        try:

            symbol = self.ibConn.tickerSymbol(tickerId)

            if self.ibConn.contracts[tickerId].m_secType in ("OPT", "FOP"):
                quote = self.ibConn.optionsData[tickerId].to_dict(orient='records')[0]
                quote['type']   = self.ibConn.contracts[tickerId].m_right
                quote['strike'] = tools.to_decimal(self.ibConn.contracts[tickerId].m_strike)
                quote["symbol_group"] = self.ibConn.contracts[tickerId].m_symbol+'_'+self.ibConn.contracts[tickerId].m_secType
                quote = tools.mark_options_values(quote)
            else:
                quote = self.ibConn.marketData[tickerId].to_dict(orient='records')[0]
                quote["symbol_group"] = tools.gen_symbol_group(symbol)

            quote["symbol"] = symbol
            quote["asset_class"] = tools.gen_asset_class(symbol)
            quote['bid']  = tools.to_decimal(quote['bid'])
            quote['ask']  = tools.to_decimal(quote['ask'])
            quote['last'] = tools.to_decimal(quote['last'])
            quote["kind"] = "QUOTE"

            # cash markets do not get RTVOLUME (handleTickString)
            if quote["asset_class"] == "CSH":
                quote['last'] = round(float((quote['bid']+quote['ask'])/2), 5)
                quote['timestamp'] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")

                # create synthetic tick
                if symbol in self.cash_ticks.keys() and quote['last'] != self.cash_ticks[symbol]:
                    self.on_tick_received(quote)
                else:
                    self.broadcast(quote, "QUOTE")

                self.cash_ticks[symbol] = quote['last']
            else:
                self.broadcast(quote, "QUOTE")

        except:
            pass

    # -------------------------------------------
    @asynctools.multitasking.task
    def on_option_computation_received(self, tickerId):
        # try:
        symbol = self.ibConn.tickerSymbol(tickerId)

        tick  = self.ibConn.optionsData[tickerId].to_dict(orient='records')[0]

        # must have values!
        for key in ('bid', 'ask', 'last', 'bidsize', 'asksize', 'lastsize',
            'volume', 'delta', 'gamma', 'vega', 'theta'):
            if tick[key] == 0:
                return

        tick['type']          = self.ibConn.contracts[tickerId].m_right
        tick['strike']        = tools.to_decimal(self.ibConn.contracts[tickerId].m_strike)
        tick["symbol_group"]  = self.ibConn.contracts[tickerId].m_symbol+'_'+self.ibConn.contracts[tickerId].m_secType
        tick['volume']        = int(tick['volume'])
        tick['bid']           = tools.to_decimal(tick['bid'])
        tick['bidsize']       = int(tick['bidsize'])
        tick['ask']           = tools.to_decimal(tick['ask'])
        tick['asksize']       = int(tick['asksize'])
        tick['last']          = tools.to_decimal(tick['last'])
        tick['lastsize']      = int(tick['lastsize'])

        tick['price']         = tools.to_decimal(tick['price'], 2)
        tick['underlying']    = tools.to_decimal(tick['underlying'])
        tick['dividend']      = tools.to_decimal(tick['dividend'])
        tick['volume']        = int(tick['volume'])
        tick['iv']            = tools.to_decimal(tick['iv'])
        tick['oi']            = int(tick['oi'])
        tick['delta']         = tools.to_decimal(tick['delta'])
        tick['gamma']         = tools.to_decimal(tick['gamma'])
        tick['vega']          = tools.to_decimal(tick['vega'])
        tick['theta']         = tools.to_decimal(tick['theta'])

        tick["symbol"]        = symbol
        tick["symbol_group"]  = tools.gen_symbol_group(symbol)
        tick["asset_class"]   = tools.gen_asset_class(symbol)

        tick = tools.mark_options_values(tick)

        # is this a really new tick?
        prev_last = 0
        prev_lastsize = 0
        if symbol in self.cash_ticks.keys():
            prev_last = self.cash_ticks[symbol]['last']
            prev_lastsize = self.cash_ticks[symbol]['lastsize']
            if tick == self.cash_ticks[symbol]:
                return

        self.cash_ticks[symbol] = dict(tick)

        # assign timestamp
        tick['timestamp'] = self.ibConn.optionsData[tickerId].index[0]
        if tick['timestamp'] == 0:
            tick['timestamp'] = datetime.utcnow().strftime(ibDataTypes['DATE_TIME_FORMAT_LONG_MILLISECS'])

        # treat as tick if last/volume changed
        if tick['last'] != prev_last or tick['lastsize'] != prev_lastsize:
            tick["kind"] = "TICK"
            self.on_tick_received(tick)

        # otherwise treat as quote
        else:
            tick["kind"] = "QUOTE"
            self.broadcast(tick, "QUOTE")

        # except:
            # pass

    # -------------------------------------------
    @asynctools.multitasking.task
    def on_orderbook_received(self, tickerId):
        orderbook = self.ibConn.marketDepthData[tickerId].dropna(
            subset=['bid', 'ask']).fillna(0).to_dict(orient='list')

        # add symbol data to list
        symbol = self.ibConn.tickerSymbol(tickerId)
        orderbook['symbol'] = symbol
        orderbook["symbol_group"]  = tools.gen_symbol_group(symbol)
        orderbook["asset_class"] = tools.gen_asset_class(symbol)
        orderbook["kind"] = "ORDERBOOK"

        # broadcast
        self.broadcast(orderbook, "ORDERBOOK")

    # -------------------------------------------
    @asynctools.multitasking.task
    def on_tick_received(self, tick):
        # data
        symbol    = tick['symbol']
        timestamp = datetime.strptime(tick['timestamp'],
            ibDataTypes["DATE_TIME_FORMAT_LONG_MILLISECS"])

        # do not act on first tick (timezone is incorrect)
        if self.first_tick:
            self.first_tick = False
            return

        try: timestamp = parse_date(timestamp)
        except: pass

        # placeholders
        if symbol not in self._raw_bars:
            self._raw_bars[symbol] = self._raw_bars['~']

        if symbol not in self._bars:
            self._bars[symbol] = self._bars['~']

        # send tick to message self.broadcast
        tick["kind"] = "TICK"
        self.broadcast(tick, "TICK")
        self.log2db(tick, "TICK")

        # add tick to raw self._bars
        tick_data = pd.DataFrame(index=['timestamp'],
            data={'timestamp':timestamp, 'last':tick['last'], 'volume':tick['lastsize']})
        tick_data.set_index(['timestamp'], inplace=True)
        _raw_bars = self._raw_bars[symbol].copy()
        _raw_bars = _raw_bars.append(tick_data)

        # add tools.resampled raw to self._bars
        ohlc = _raw_bars['last'].resample('1T').ohlc()
        vol  = _raw_bars['volume'].resample('1T').sum()

        opened_bar = ohlc
        opened_bar['volume'] = vol

        # add bar to self._bars object
        previous_bar_count = len(self._bars[symbol])
        self._bars[symbol] = self._bars[symbol].append(opened_bar)
        self._bars[symbol] = self._bars[symbol].groupby(self._bars[symbol].index).last()

        if len(self._bars[symbol].index) > previous_bar_count:

            bar = self._bars[symbol].to_dict(orient='records')[0]
            bar["symbol"]      = symbol
            bar["symbol_group"] = tick['symbol_group']
            bar["asset_class"] = tick['asset_class']
            bar["timestamp"]   = self._bars[symbol].index[0].strftime(
                ibDataTypes["DATE_TIME_FORMAT_LONG"])

            bar["kind"] = "BAR"
            self.broadcast(bar, "BAR")
            self.log2db(bar, "BAR")

            self._bars[symbol] = self._bars[symbol][-1:]
            _raw_bars.drop(_raw_bars.index[:], inplace=True)
            self._raw_bars[symbol] = _raw_bars

    # -------------------------------------------
    def broadcast(self, data, kind):
        string2send = "%s %s" % (self.args["zmqtopic"], json.dumps(data))
        # print(kind, string2send)
        try:
            self.socket.send_string(string2send)
        except:
            pass

    # -------------------------------------------
    def log2db(self, data, kind):
        if self.args['dbskip']:
            return

        # connect to mysql per call (thread safe)
        dbconn = self.get_mysql_connection()
        dbcurr = dbconn.cursor()

        # set symbol details
        symbol_id = 0
        symbol = data["symbol"].replace("_"+data["asset_class"], "")

        if symbol in self.symbol_ids.keys():
            symbol_id = self.symbol_ids[symbol]
        else:
            symbol_id = get_symbol_id(data["symbol"], dbconn, dbcurr, self.ibConn)
            self.symbol_ids[symbol] = symbol_id

        # insert to db
        if kind == "TICK":
            try: mysql_insert_tick(data, symbol_id, dbcurr)
            except: pass
        elif kind == "BAR":
            try: mysql_insert_bar(data, symbol_id, dbcurr)
            except: pass

        # commit
        try: dbconn.commit()
        except: pass

        # disconect from mysql
        dbcurr.close()
        dbconn.close()

    # -------------------------------------------
    def run(self):
        """Starts the blotter

        Connects to the TWS/GW, processes and logs market data,
        and broadcast it over TCP via ZeroMQ (which algo subscribe to)
        """

        self._check_unique_blotter()

        # connect to mysql
        self.mysql_connect()

        self.context = zmq.Context(zmq.REP)
        self.socket  = self.context.socket(zmq.PUB)
        self.socket.bind("tcp://*:"+str(self.args['zmqport']))

        db_modified    = 0
        contracts      = []
        prev_contracts = []
        first_run      = True

        self.log_blotter.info("Connecting to Interactive Brokers...")
        self.ibConn = ezIBpy()
        self.ibConn.ibCallback = self.ibCallback

        while not self.ibConn.connected:
            self.ibConn.connect(clientId=int(self.args['ibclient']),
                port=int(self.args['ibport']), host=str(self.args['ibserver']))
            time.sleep(1)
            if not self.ibConn.connected:
                print('*', end="", flush=True)
        self.log_blotter.info("Connection established...")

        try:
            while True:

                if not os.path.exists(self.args['symbols']):
                    pd.DataFrame(columns=['symbol','sec_type','exchange',
                        'currency','expiry','strike','opt_type']
                    ).to_csv(self.args['symbols'], header=True, index=False)
                    tools.chmod(self.args['symbols'])
                else:
                    time.sleep(0.1)

                    # read db properties
                    db_data = os.stat(self.args['symbols'])
                    db_size = db_data.st_size
                    db_last_modified = db_data.st_mtime

                    # empty file
                    if db_size == 0:
                        if len(prev_contracts) > 0:
                            self.log_blotter.info('Cancel market data...')
                            self.ibConn.cancelMarketData()
                            time.sleep(0.1)
                            prev_contracts = []
                        continue

                    # modified?
                    if (first_run == False) & (db_last_modified == db_modified):
                        continue

                    # continue...
                    db_modified = db_last_modified

                    # read contructs db
                    df = pd.read_csv(self.args['symbols'], header=0)
                    if len(df.index) == 0:
                        continue

                    # removed expired
                    df = df[
                        ( (df['expiry'] <1000000) & (df['expiry']>=int(datetime.now().strftime('%Y%m'  ))) ) |
                        ( (df['expiry']>=1000000) & (df['expiry']>=int(datetime.now().strftime('%Y%m%d'))) ) |
                        npisnan(df['expiry'])
                    ]

                    # fix expiry formatting (no floats)
                    df['expiry'] = df['expiry'].fillna(0).astype(int).astype(str)
                    df.loc[df['expiry']=="0", 'expiry'] = ""

                    df.fillna("", inplace=True)
                    df.to_csv(self.args['symbols'], header=True, index=False)
                    tools.chmod(self.args['symbols'])

                    df = df[df['symbol'].str.contains("#")==False] # ignore commentee
                    contracts = [tuple(x) for x in df.values]

                    if first_run:
                        first_run = False

                    else:
                        if contracts != prev_contracts:
                            # cancel market data for removed contracts
                            for contract in prev_contracts:
                                if contract not in contracts:
                                    self.ibConn.cancelMarketData(self.ibConn.createContract(contract))
                                    if self.args['orderbook']:
                                        self.ibConn.cancelMarketDepth(self.ibConn.createContract(contract))
                                    time.sleep(0.1)
                                    contract_string = self.ibConn.contractString(contract).split('_')[0]
                                    self.log_blotter.info('Contract Removed ['+contract_string+']')

                    # request market data
                    for contract in contracts:
                        if contract not in prev_contracts:
                            self.ibConn.requestMarketData(self.ibConn.createContract(contract))
                            if self.args['orderbook']:
                                self.ibConn.requestMarketDepth(self.ibConn.createContract(contract))
                            time.sleep(0.1)
                            contract_string = self.ibConn.contractString(contract).split('_')[0]
                            self.log_blotter.info('Contract Added ['+contract_string+']')

                    # update latest contracts
                    prev_contracts = contracts

                time.sleep(2)


        except (KeyboardInterrupt, SystemExit):
            self.quitting = True # don't display connection errors on ctrl+c
            # print("\n\n>>> Interrupted with Ctrl-c...")
            print("\n\n>>> Interrupted with Ctrl-c...\n(waiting for running threads to be completed)\n")
            # asynctools.multitasking.killall() # stop now
            asynctools.multitasking.wait_for_tasks() # wait for threads to complete
            sys.exit(1)


    # -------------------------------------------
    # CLIENT / STATIC
    # -------------------------------------------
    def _fix_history_sequence(self, df, table):
        """ fix out-of-sequence ticks/bars """

        # remove "Unnamed: x" columns
        cols = df.columns[df.columns.str.startswith('Unnamed:')].tolist()
        df.drop(cols, axis=1, inplace=True)

        # remove future dates
        df['datetime'] = pd.to_datetime(df['datetime'], utc=True)
        blacklist = df[df['datetime'] > datetime.utcnow()]
        df = df.loc[set(df.index) - set(blacklist) ] #.tail()

        # loop through data, symbol by symbol
        dfs = []
        bad_ids = [blacklist['id'].values.tolist()]

        for symbol_id in list(df['symbol_id'].unique()):

            data = df[df['symbol_id'] == symbol_id].copy()

            # sort by id
            data.sort_values('id', axis=0, ascending=True, inplace=False)

            # convert index to column
            data.loc[:, "ix"] = data.index
            data.reset_index(inplace=True)

            # find out of sequence ticks/bars
            malformed = data.shift(1)[ (data['id'] > data['id'].shift(1)) & (data['datetime'] < data['datetime'].shift(1)) ]

            # cleanup rows
            if len(malformed.index) == 0:
                # if all rows are in sequence, just remove last row
                dfs.append(data)
            else:
                # remove out of sequence rows + last row from data
                index = [x for x in data.index.values if x not in malformed['ix'].values]
                dfs.append( data.loc[index] )

                # add to bad id list (to remove from db)
                bad_ids.append(list(malformed['id'].values))

        # combine all lists
        data = pd.concat(dfs)

        # flatten bad ids
        bad_ids = sum(bad_ids, [])

        # remove bad ids from db
        if len(bad_ids) > 0:
            bad_ids = list(map(str, map(int, bad_ids)))
            self.dbcurr.execute("DELETE FROM greeks WHERE %s IN (%s)" % (table.lower()[:-1]+"_id", ",".join(bad_ids)))
            self.dbcurr.execute("DELETE FROM "+table.lower()+" WHERE id IN (%s)" % (",".join(bad_ids)))
            try: self.dbconn.commit()
            except: self.dbconn.rollback()

        # return
        return data.drop(['id', 'ix', 'index'], axis=1)

    # -------------------------------------------
    def history(self, symbols, start, end=None, resolution="1T", tz="UTC", continuous=True):
        # load runtime/default data
        if isinstance(symbols, str):
            symbols = symbols.split(',')

        # work with symbol groups
        # symbols = list(map(tools.gen_symbol_group, symbols))
        symbol_groups = list(map(tools.gen_symbol_group, symbols))
        # print(symbols)

        # convert datetime to string for MySQL
        try: start = start.strftime(ibDataTypes["DATE_TIME_FORMAT_LONG_MILLISECS"])
        except: pass

        if end is not None:
            try: end = end.strftime(ibDataTypes["DATE_TIME_FORMAT_LONG_MILLISECS"])
            except: pass

        # connect to mysql
        self.mysql_connect()

        # --- build query
        table = 'ticks' if resolution[-1] in ("K", "V", "S") else 'bars'

        query = """SELECT tbl.*,
            CONCAT(s.`symbol`, "_", s.`asset_class`) as symbol, s.symbol_group, s.asset_class, s.expiry,
            g.price AS opt_price, g.underlying AS opt_underlying, g.dividend AS opt_dividend,
            g.volume AS opt_volume, g.iv AS opt_iv, g.oi AS opt_oi,
            g.delta AS opt_delta, g.gamma AS opt_gamma,
            g.theta AS opt_theta, g.vega AS opt_vega
            FROM `{TABLE}` tbl LEFT JOIN `symbols` s ON tbl.symbol_id = s.id
            LEFT JOIN `greeks` g ON tbl.id = g.{TABLE_ID}
            WHERE (`datetime` >= "{START}"{END_SQL}) """.replace(
            '{START}', start).replace('{TABLE}', table).replace('{TABLE_ID}', table[:-1]+'_id')

        if end is not None:
            query = query.replace('{END_SQL}', ' AND `datetime` <= "{END}"')
            query = query.replace('{END}', end)
        else:
            query = query.replace('{END_SQL}', '')

        if symbols[0].strip() != "*":
            if continuous:
                query += """ AND ( s.`symbol_group` in ("{SYMBOL_GROUPS}") or CONCAT(s.`symbol`, "_", s.`asset_class`) IN ("{SYMBOLS}") ) """
                query = query.replace('{SYMBOLS}', '","'.join(symbols)).replace('{SYMBOL_GROUPS}', '","'.join(symbol_groups))
            else:
                query += """ AND ( CONCAT(s.`symbol`, "_", s.`asset_class`) IN ("{SYMBOLS}") ) """
                query = query.replace('{SYMBOLS}', '","'.join(symbols))
        # --- end build query

        # get data using pandas
        data = pd.read_sql(query, self.dbconn) #.dropna()

        # no data in db
        if len(data.index) == 0:
            return data

        # clearup records that are out of sequence
        data = self._fix_history_sequence(data, table)

        # setup dataframe
        return prepare_history(data=data, resolution=resolution, tz=tz, continuous=True)

    # -------------------------------------------
    def stream(self, symbols, tick_handler=None, bar_handler=None, \
        quote_handler=None, book_handler=None, tz="UTC"):
        # load runtime/default data
        if isinstance(symbols, str):
            symbols = symbols.split(',')
        symbols = list(map(str.strip, symbols))

        # connect to zeromq self.socket
        self.context = zmq.Context()
        sock = self.context.socket(zmq.SUB)
        sock.setsockopt_string(zmq.SUBSCRIBE, "")
        sock.connect('tcp://127.0.0.1:'+str(self.args['zmqport']))

        try:
            while True:
                message = sock.recv_string()

                if (self.args["zmqtopic"] in message):
                    message = message.split(self.args["zmqtopic"])[1].strip()
                    data    = json.loads(message)

                    if data['symbol'] not in symbols:
                        continue

                    # convert None to np.nan !!
                    data.update((k, npnan) for k,v in data.items() if v is None)

                    # quote
                    if data['kind'] == "ORDERBOOK":
                        if book_handler is not None:
                            book_handler(data)
                            continue
                    # quote
                    if data['kind'] == "QUOTE":
                        if quote_handler is not None:
                            quote_handler(data)
                            continue

                    try: data["datetime"] = parse_date(data["timestamp"])
                    except: pass

                    df = pd.DataFrame(index=[0], data=data)
                    df.set_index('datetime', inplace=True)
                    df.index = pd.to_datetime(df.index, utc=True)
                    df.drop(["timestamp", "kind"], axis=1, inplace=True)

                    try:
                        df.index = df.index.tz_convert(tz)
                    except:
                        df.index = df.index.tz_localize('UTC').tz_convert(tz)

                    # add options columns
                    df = tools.force_options_columns(df)

                    if data['kind'] == "TICK":
                        if tick_handler is not None:
                            tick_handler(df)
                    elif data['kind'] == "BAR":
                        if bar_handler is not None:
                            bar_handler(df)

        except (KeyboardInterrupt, SystemExit):
            print("\n\n>>> Interrupted with Ctrl-c...\n(waiting for running threads to be completed)\n")
            print(".\n.\n.\n")
            # asynctools.multitasking.killall() # stop now
            asynctools.multitasking.wait_for_tasks() # wait for threads to complete
            sys.exit(1)

    # -------------------------------------------
    def drip(self, data, handler):
        try:
            for i in range(len(data)):
                handler(data.iloc[i:i + 1])
                time.sleep(.1)

            asynctools.multitasking.wait_for_tasks()
            print("\n\n>>> Backtesting Completed.")

        except (KeyboardInterrupt, SystemExit):
            print("\n\n>>> Interrupted with Ctrl-c...\n(waiting for running threads to be completed)\n")
            print(".\n.\n.\n")
            # asynctools.multitasking.killall() # stop now
            asynctools.multitasking.wait_for_tasks() # wait for threads to complete
            sys.exit(1)

    # ---------------------------------------
    def backfill(self, data, resolution, start, end=None):
        """
        Backfills missing historical data

        :Optional:
            data : pd.DataFrame
                Minimum required bars for backfill attempt
            resolution : str
                Algo resolution
            start: datetime
                Backfill start date (YYYY-MM-DD [HH:MM:SS[.MS]).
            end: datetime
                Backfill end date (YYYY-MM-DD [HH:MM:SS[.MS]). Default is None
        :Returns:
            status : mixed
                False for "won't backfill" / True for "backfilling, please wait"
        """

        data.sort_index(inplace=True)

        # currenly only supporting minute-data
        if resolution[-1] in ("K", "V"):
            self.backfilled = True
            return None

        # missing history?
        start_date = parse_date(start)
        end_date   = parse_date(end) if end else datetime.utcnow()

        if len(data.index) == 0:
            first_date = datetime.utcnow()
            last_date  = datetime.utcnow()
        else:
            first_date = tools.datetime64_to_datetime(data.index.values[0])
            last_date  = tools.datetime64_to_datetime(data.index.values[-1])

        ib_lookback = None
        if start_date < first_date:
            ib_lookback = tools.ib_duration_str(start_date)
        elif end_date > last_date:
            ib_lookback = tools.ib_duration_str(last_date)

        if not ib_lookback:
            self.backfilled = True
            return None

        self.backfill_resolution = "1 min" if resolution[-1] not in ("K", "V", "S") else "1 sec"
        self.log_blotter.warning("Backfilling historical data from IB...")

        # request parameters
        params = {
            "lookback": ib_lookback,
            "resolution": self.backfill_resolution,
            "data": "TRADES",
            "rth": False,
            "end_datetime": None,
            "csv_path": None
        }

        # if connection is active - request data
        self.ibConn.requestHistoricalData(**params)

        # wait for backfill to complete
        while not self.backfilled:
            time.sleep(0.01)

        # otherwise, pass the parameters to the caller
        return True

    # -------------------------------------------
    def register(self, instruments):

        if isinstance(instruments, dict):
            instruments = list(instruments.values())

        if not isinstance(instruments, list):
            return

        db = pd.read_csv(self.args['symbols'], header=0).fillna("")

        instruments = pd.DataFrame(instruments)
        instruments.columns = db.columns
        # instruments['expiry'] = instruments['expiry'].astype(int).astype(str)

        db = db.append(instruments)
        # db['expiry'] = db['expiry'].astype(int)
        db = db.drop_duplicates(keep="first")

        db.to_csv(self.args['symbols'], header=True, index=False)
        tools.chmod(self.args['symbols'])


    # -------------------------------------------
    def get_mysql_connection(self):
        if self.args['dbskip']:
            return

        return pymysql.connect(
            host   = str(self.args['dbhost']),
            port   = int(self.args['dbport']),
            user   = str(self.args['dbuser']),
            passwd = str(self.args['dbpass']),
            db     = str(self.args['dbname'])
        )

    def mysql_connect(self):

        # already connected?
        if self.dbcurr is not None or self.dbconn is not None:
            return

        # connect to mysql
        self.dbconn = self.get_mysql_connection()
        self.dbcurr = self.dbconn.cursor()

        # check for db schema
        self.dbcurr.execute("SHOW TABLES")
        tables = [ table[0] for table in self.dbcurr.fetchall() ]

        if "bars" in tables and "ticks" in tables and \
            "symbols" in tables and "trades" in tables and \
            "greeks" in tables and "_version_" in tables:
                self.dbcurr.execute("SELECT version FROM `_version_`")
                db_version = self.dbcurr.fetchone()
                if db_version is not None and __version__ == db_version[0]:
                    return

        # create database schema
        self.dbcurr.execute(open(path['library']+'/schema.sql', "rb" ).read())
        try:
            self.dbconn.commit()

            # update version #
            sql = "TRUNCATE TABLE _version_; INSERT INTO _version_ (`version`) VALUES (%s)"
            self.dbcurr.execute(sql, (__version__))
            self.dbconn.commit()

            # unless we do this, there's a problem with curr.fetchX()
            self.dbcurr.close()
            self.dbconn.close()

            # re-connect to mysql
            self.dbconn = self.get_mysql_connection()
            self.dbcurr = self.dbconn.cursor()

        except:
            self.dbconn.rollback()
            self.log_blotter.error("Cannot create database schema")
            self._remove_cached_args()
            sys.exit(1)



    # ===========================================
    # Utility functions --->
    # ===========================================

    # -------------------------------------------


# -------------------------------------------
def load_blotter_args(blotter_name=None, logger=None):
    """ Load running blotter's settings (used by clients)

    :Parameters:
        blotter_name : str
            Running Blotter's name (defaults to "auto-detect")
        logger : object
            Logger to be use (defaults to Blotter's)

    :Returns:
        args : dict
            Running Blotter's arguments
    """
    if logger is None:
        logger= tools.createLogger(__name__, logging.WARNING)

    # find specific name
    if blotter_name is not None: # and blotter_name != 'auto-detect':
        args_cache_file = tempfile.gettempdir()+"/"+blotter_name.lower()+".qtpylib"
        if not os.path.exists(args_cache_file):
            logger.critical("Cannot connect to running Blotter [%s]" % (blotter_name))
            if os.isatty(0): sys.exit(0)
            return

    # no name provided - connect to last running
    else:
        blotter_files = sorted(glob.glob(tempfile.gettempdir()+"/*.qtpylib"), key=os.path.getmtime)
        if len(blotter_files) == 0:
            logger.critical("Cannot connect to running Blotter [%s]" % (blotter_name))
            if os.isatty(0): sys.exit(0)
            return

        args_cache_file = blotter_files[-1]

    args = pickle.load( open(args_cache_file, "rb" ) )
    args['as_client'] = True

    return args

# -------------------------------------------
def get_symbol_id(symbol, dbconn, dbcurr, ibConn=None):
    """
    Retrives symbol's ID from the Database or create it if it doesn't exist

    :Parameters:
        symbol : str
            Instrument symbol
        dbconn : object
            Database connection to be used
        dbcurr : object
            Database cursor to be used

    :Optional:
        ibConn : object
            ezIBpy object (used for determining futures/options expiration)

    :Returns:
        symbol_id : int
            Symbol ID
    """
    def _get_contract_expiry(symbol, ibConn=None):
        # parse w/p ibConn
        if ibConn is None or isinstance(symbol, str):
            return tools.contract_expiry_from_symbol(symbol)

        # parse with ibConn
        contract_details = ibConn.contractDetails(symbol)["m_summary"]
        if contract_details["m_expiry"] == "":
            ibConn.createContract(symbol)
            return _get_contract_expiry(symbol, ibConn)

        if contract_details["m_expiry"]:
            return datetime.strptime(str(contract_details["m_expiry"]), '%Y%m%d').strftime("%Y-%m-%d")

        return contract_details["m_expiry"]


    # start
    asset_class  = tools.gen_asset_class(symbol)
    symbol_group = tools.gen_symbol_group(symbol)
    clean_symbol = symbol.replace("_"+asset_class, "")
    expiry = None

    if asset_class in ("FUT", "OPT", "FOP"):
        expiry = _get_contract_expiry(symbol, ibConn)

        # look for symbol w/ expiry
        sql = """SELECT id FROM `symbols` WHERE
            `symbol`=%s AND `symbol_group`=%s AND `asset_class`=%s  AND `expiry`=%s LIMIT 1"""
        dbcurr.execute(sql, (clean_symbol, symbol_group, asset_class, expiry))

    else:
        # look for symbol w/o expiry
        sql = """SELECT id FROM `symbols` WHERE
            `symbol`=%s AND `symbol_group`=%s AND `asset_class`=%s LIMIT 1"""
        dbcurr.execute(sql, (clean_symbol, symbol_group, asset_class))

    row = dbcurr.fetchone()

    # symbol already in db
    if row is not None:
        return row[0]

    # symbol/expiry not in db... insert new/update expiry
    else:
        # need to update the expiry?
        if expiry is not None:
            sql = """SELECT id FROM `symbols` WHERE
                `symbol`=%s AND `symbol_group`=%s AND `asset_class`=%s LIMIT 1"""
            dbcurr.execute(sql, (clean_symbol, symbol_group, asset_class))

            row = dbcurr.fetchone()
            if row is not None:
                sql = "UPDATE `symbols` SET `expiry`='"+str(expiry)+"' WHERE id="+str(row[0])
                dbcurr.execute(sql)
                try: dbconn.commit()
                except: return
                return int(row[0])

        # insert new symbol
        sql = """INSERT IGNORE INTO `symbols`
            (`symbol`, `symbol_group`, `asset_class`, `expiry`) VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE `symbol`=`symbol`, `expiry`=%s
        """

        dbcurr.execute(sql, (clean_symbol, symbol_group, asset_class, expiry, expiry))
        try: dbconn.commit()
        except: return

        return dbcurr.lastrowid


# -------------------------------------------
def mysql_insert_tick(data, symbol_id, dbcurr):

    sql = """INSERT IGNORE INTO `ticks` (`datetime`, `symbol_id`,
        `bid`, `bidsize`, `ask`, `asksize`, `last`, `lastsize`)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE `symbol_id`=`symbol_id`
    """
    dbcurr.execute(sql, (data["timestamp"], symbol_id,
        float(data["bid"]), int(data["bidsize"]),
        float(data["ask"]), int(data["asksize"]),
        float(data["last"]), int(data["lastsize"])
    ))

    # add greeks
    if dbcurr.lastrowid and data["asset_class"] in ("OPT", "FOP"):
        greeks_sql = """INSERT IGNORE INTO `greeks` (
            `tick_id`, `price`, `underlying`, `dividend`, `volume`,
            `iv`, `oi`, `delta`, `gamma`, `theta`, `vega`)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        try:
            dbcurr.execute(greeks_sql, (dbcurr.lastrowid,
                round(float(data["opt_price"]), 2), round(float(data["opt_underlying"]), 5),
                float(data["opt_dividend"]),int(data["opt_volume"]),
                float(data["opt_iv"]), float(data["opt_oi"]),
                float(data["opt_delta"]), float(data["opt_gamma"]),
                float(data["opt_theta"]), float(data["opt_vega"]),
            ))
        except:
            pass


# -------------------------------------------
def mysql_insert_bar(data, symbol_id, dbcurr):
    sql = """INSERT IGNORE INTO `bars`
        (`datetime`, `symbol_id`, `open`, `high`, `low`, `close`, `volume`)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            `open`=%s, `high`=%s, `low`=%s, `close`=%s, `volume`=`volume`+%s
    """
    dbcurr.execute(sql, (data["timestamp"], symbol_id,
        float(data["open"]),float(data["high"]),float(data["low"]),float(data["close"]),int(data["volume"]),
        float(data["open"]),float(data["high"]),float(data["low"]),float(data["close"]),int(data["volume"])
    ))

    # add greeks
    if dbcurr.lastrowid and data["asset_class"] in ("OPT", "FOP"):
        greeks_sql = """INSERT IGNORE INTO `greeks` (
            `bar_id`, `price`, `underlying`, `dividend`, `volume`,
            `iv`, `oi`, `delta`, `gamma`, `theta`, `vega`)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        greeks = cash_ticks[data['symbol']]
        try:
            dbcurr.execute(greeks_sql, (dbcurr.lastrowid,
                round(float(greeks["opt_price"]), 2), round(float(greeks["opt_underlying"]), 5),
                float(greeks["opt_dividend"]),int(greeks["opt_volume"]),
                float(greeks["opt_iv"]), float(greeks["opt_oi"]),
                float(greeks["opt_delta"]), float(greeks["opt_gamma"]),
                float(greeks["opt_theta"]), float(greeks["opt_vega"]),
            ))
        except:
            pass

# -------------------------------------------
def prepare_history(data, resolution="1T", tz="UTC", continuous=True):

    # setup dataframe
    data.set_index('datetime', inplace=True)
    data.index = pd.to_datetime(data.index, utc=True)
    data['expiry'] = pd.to_datetime(data['expiry'], utc=True)

    # remove _STK from symbol to match ezIBpy's formatting
    data['symbol'] = data['symbol'].str.replace("_STK", "")

    # force options columns
    data = tools.force_options_columns(data)

    # construct continuous contracts for futures
    if continuous and resolution[-1] not in ("K", "V", "S"):
        all_dfs = [ data[data['asset_class']!='FUT'] ]

        # generate dict of df per future
        futures_symbol_groups = list( data[data['asset_class']=='FUT']['symbol_group'].unique() )
        for key in futures_symbol_groups:
            future_group = data[data['symbol_group']==key]
            continuous = futures.create_continuous_contract(future_group, resolution)
            all_dfs.append(continuous)

        # make one df again
        data = pd.concat(all_dfs)

    data = tools.resample(data, resolution, tz)
    return data

# -------------------------------------------
if __name__ == "__main__":
    blotter = Blotter()
    blotter.run()