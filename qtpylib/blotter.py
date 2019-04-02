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
import atexit
import json
import logging
import os
import pickle

import sys
import tempfile
import time
import glob
import subprocess

from datetime import datetime
from abc import ABCMeta

import zmq
import pandas as pd
from dateutil.parser import parse as parse_date

from numpy import (
    isnan as np_isnan,
    nan as np_nan,
    int64 as np_int64
)

from ezibpy import (
    ezIBpy, dataTypes as ibDataTypes
)

from qtpylib import (
    tools, path, futures
)

# =============================================
# check min, python version
if sys.version_info < (3, 4):
    raise SystemError("QTPyLib requires Python version >= 3.4")

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

        name : str
            name of the blotter (used by other modules)
        symbols : list
            IB contracts CSV database (default: ./symbols.csv)
        ibport : int
            TWS/GW Port to use (default: 4001)
        ibclient : int
            TWS/GW Client ID (default: 999)
        ibserver : str
            IB TWS/GW Server hostname (default: localhost)
        ibaccount : str
            Specific IB accunt to use (default: None / IB Default)
        zmqport : str
            ZeroMQ Port to use (default: 12345)
        zmqtopic : str
            ZeroMQ string to use (default: _qtpylib_BLOTTERNAME_)
        orderbook : bool
            Get Order Book (Market Depth) data (default: False)
        datastore : str
            Datastore engine: SQLAlchemy connection string or pystore[://path]
            (Default: None)
        store : str
            Store ticks/bars if datastore is enabled? (default ticks+bars)
    """

    __metaclass__ = ABCMeta

    def __init__(self, name=None, symbols="symbols.csv",
                 ibport=4001, ibclient=999, ibserver="localhost",
                 ibaccount=None, datastore=None, store="ticks+bars",
                 orderbook=False, zmqport="12345", zmqtopic=None, **kwargs):

        # whats my name?
        self.name = str(self.__class__).split('.')[-1].split("'")[0].lower()
        if name is not None:
            self.name = name

        # initilize class logger
        self.log_blotter = logging.getLogger(__name__)

        # do not act on first tick (timezone is incorrect)
        self.first_tick = True

        self._bars = pd.DataFrame(
            columns=['open', 'high', 'low', 'close', 'volume'])
        self._bars.index.names = ['datetime']
        self._bars.index = pd.to_datetime(self._bars.index, utc=True)
        # self._bars.index = self._bars.index.tz_convert(settings['timezone'])
        self._bars = {"~": self._bars}

        self._raw_bars = pd.DataFrame(columns=['last', 'volume'])
        self._raw_bars.index.names = ['datetime']
        self._raw_bars.index = pd.to_datetime(self._raw_bars.index, utc=True)
        self._raw_bars = {"~": self._raw_bars}

        # global objects
        self.datastore = None
        self.zmq = None
        self.socket = None
        self.ibConn = None

        self.symbol_ids = {}  # cache
        self.cash_ticks = cash_ticks  # outside cache
        self.rtvolume = set()  # has RTVOLUME?

        # -------------------------------
        # work default values
        # -------------------------------
        if zmqtopic is None:
            zmqtopic = "_qtpylib_" + str(self.name.lower()) + "_"

        # if no path given for symbols' csv, use same dir
        if symbols == "symbols.csv":
            symbols = path['caller'] + '/' + symbols
        # -------------------------------

        # override args with any (non-default) command-line args
        self.args = {arg: val for arg, val in locals().items(
        ) if arg not in ('__class__', 'self', 'kwargs')}
        self.args.update(kwargs)
        self.args.update(self.load_cli_args())

        self.args["store"] = self.args["store"].lower()
        if self.args["store"] == "all":
            self.args["store"] = "ticks+bars"

        # read cached args to detect duplicate blotters
        self.duplicate_run = False
        self.cahced_args = {}
        self.args_cache_file = "%s/%s.qtpylib" % (
            tempfile.gettempdir(), self.name)
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

        if self.args['datastore']:
            self.log_blotter.info("Disconnecting from Datastore...")
            try:
                self.datastore.close()
            except Exception:
                pass

        if terminate:
            os._exit(0)

    # -------------------------------------------
    @staticmethod
    def _detect_running_blotter(name):
        return name

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

    # -------------------------------------------
    def load_cli_args(self):
        parser = argparse.ArgumentParser(
            description='QTPyLib Blotter',
            formatter_class=argparse.ArgumentDefaultsHelpFormatter)

        parser.add_argument('--symbols', default=self.args['symbols'],
                            help='IB contracts CSV database', required=False)
        parser.add_argument('--ibport', default=self.args['ibport'],
                            help='TWS/GW Port to use', required=False)
        parser.add_argument('--ibclient', default=self.args['ibclient'],
                            help='TWS/GW Client ID', required=False)
        parser.add_argument('--ibserver', default=self.args['ibserver'],
                            help='IB TWS/GW Server hostname', required=False)
        parser.add_argument('--ibaccount', default=self.args['ibaccount'],
                            help='Specific IB account to use', required=False)
        parser.add_argument('--zmqport', default=self.args['zmqport'],
                            help='ZeroMQ Port to use', required=False)
        parser.add_argument('--orderbook', action='store_true',
                            help='Get Order Book (Market Depth) data',
                            required=False)
        parser.add_argument('--datastore', default=self.args['datastore'],
                            help='Data storage engine', required=False)
        parser.add_argument('--store', default=self.args['store'],
                            help='Store ticks/bars in DB?', required=False)

        # only return non-default cmd line args
        # (meaning only those actually given)
        cmd_args, _ = parser.parse_known_args()
        args = {arg: val for arg, val in vars(
            cmd_args).items() if val != parser.get_default(arg)}
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

            # errorCode can be None...
            if 1100 <= msg.errorCode < 2200 or msg.errorCode == 0:
                self.log_blotter.warning(
                    '[IB #%d] %s', msg.errorCode, msg.errorMsg)
            elif msg.errorCode not in (502, 504):  # connection error
                self.log_blotter.error(
                    '[IB #%d] %s', msg.errorCode, msg.errorMsg)

    # -------------------------------------------
    def on_ohlc_received(self, msg, kwargs):
        """ handles historical data download """
        symbol = self.ibConn.tickerSymbol(msg.reqId)

        if kwargs["completed"]:
            self.backfilled_symbols.append(symbol)
            tickers = set({v: k for k, v in self.ibConn.tickerIds.items()
                           if v.upper() != "SYMBOL"}.keys())
            if tickers == set(self.backfilled_symbols):
                self.backfilled = True
                print(".")

            try:
                self.ibConn.cancelHistoricalData(
                    self.ibConn.contracts[msg.reqId])
            except Exception:
                pass

        else:
            data = {
                "symbol": symbol,
                "symbol_group": tools.gen_symbol_group(symbol),
                "asset_class": tools.gen_asset_class(symbol),
                "timestamp": tools.datetime_to_timezone(
                    datetime.fromtimestamp(int(msg.date)), tz="UTC"
                ).strftime("%Y-%m-%d %H:%M:%S"),
            }

            # incmoing second data
            if "sec" in self.backfill_resolution:
                data["last"] = tools.to_decimal(msg.close)
                data["lastsize"] = int(msg.volume)  # msg.count?
                data["bid"] = 0
                data["bidsize"] = 0
                data["ask"] = 0
                data["asksize"] = 0
                data["kind"] = "TICK"
            else:
                data["open"] = tools.to_decimal(msg.open)
                data["high"] = tools.to_decimal(msg.high)
                data["low"] = tools.to_decimal(msg.low)
                data["close"] = tools.to_decimal(msg.close)
                data["volume"] = int(msg.volume)
                data["kind"] = "BAR"

            # print(data)

            # store in db
            if (data["kind"] == "TICK" and "tick" in self.args['store']) or \
                    (data["kind"] == "BAR" and "bar" in self.args['store']):
                self.datastore.store(data=data, kind=data["kind"])

    # -------------------------------------------

    def on_tick_received(self, tick):
        # data
        symbol = tick['symbol']
        timestamp = datetime.strptime(tick['timestamp'], ibDataTypes[
            "DATE_TIME_FORMAT_LONG_MILLISECS"])

        # do not act on first tick (timezone is incorrect)
        if self.first_tick:
            self.first_tick = False
            return

        try:
            timestamp = parse_date(timestamp)
        except Exception:
            pass

        # placeholders
        if symbol not in self._raw_bars:
            self._raw_bars[symbol] = self._raw_bars['~']

        if symbol not in self._bars:
            self._bars[symbol] = self._bars['~']

        # send tick to message self.broadcast
        tick["kind"] = "TICK"
        self.broadcast(tick, "TICK")
        if "tick" in self.args['store']:
            if "tick" in self.args['store']:
                self.datastore.store(data=tick, kind="TICK",
                                     greeks=self.cash_ticks[symbol])

        # add tick to raw self._bars
        tick_data = pd.DataFrame(index=['timestamp'],
                                 data={'timestamp': timestamp,
                                       'last': tick['last'],
                                       'volume': tick['lastsize']})
        tick_data.set_index(['timestamp'], inplace=True)
        _raw_bars = self._raw_bars[symbol].copy()
        _raw_bars = _raw_bars.append(tick_data)

        # add tools.resampled raw to self._bars
        ohlc = _raw_bars['last'].resample('1T').ohlc()
        vol = _raw_bars['volume'].resample('1T').sum()
        vol = _raw_bars['volume'].resample('1T').sum()

        opened_bar = ohlc
        opened_bar['volume'] = vol

        # add bar to self._bars object
        previous_bar_count = len(self._bars[symbol])
        self._bars[symbol] = self._bars[symbol].append(opened_bar)
        self._bars[symbol] = self._bars[symbol].groupby(
            self._bars[symbol].index).last()

        if len(self._bars[symbol].index) > previous_bar_count:

            bar = self._bars[symbol].to_dict(orient='records')[0]
            bar["symbol"] = symbol
            bar["symbol_group"] = tick['symbol_group']
            bar["asset_class"] = tick['asset_class']
            bar["timestamp"] = self._bars[symbol].index[0].strftime(
                ibDataTypes["DATE_TIME_FORMAT_LONG"])

            bar["kind"] = "BAR"
            self.broadcast(bar, "BAR")
            if "tick" in self.args['store']:
                self.datastore.store(data=bar, kind="BAR",
                                     greeks=self.cash_ticks[symbol])

            self._bars[symbol] = self._bars[symbol][-1:]
            _raw_bars.drop(_raw_bars.index[:], inplace=True)
            self._raw_bars[symbol] = _raw_bars

    # -------------------------------------------

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
                "symbol": symbol,
                "symbol_group": tools.gen_symbol_group(symbol),  # ES_F, ...
                "asset_class": tools.gen_asset_class(symbol),
                "timestamp": kwargs['tick']['time'],
                "last": tools.to_decimal(kwargs['tick']['last']),
                "lastsize": int(kwargs['tick']['size']),
                "bid": tools.to_decimal(kwargs['tick']['bid']),
                "ask": tools.to_decimal(kwargs['tick']['ask']),
                "bidsize": int(kwargs['tick']['bidsize']),
                "asksize": int(kwargs['tick']['asksize']),
                # "wap": kwargs['tick']['wap'],
            }

        # for instruments that AREN'T receive RTVOLUME events (exclude options)
        elif symbol not in self.rtvolume and \
                self.ibConn.contracts[tickerId].m_secType not in (
                    "OPT", "FOP"):

            tick = self.ibConn.marketData[tickerId]

            if not tick.empty and (
                    tick['last'].values[-1] > 0 < tick['lastsize'].values[-1]):
                data = {
                    # available data from ib
                    "symbol": symbol,
                    # ES_F, ...
                    "symbol_group": tools.gen_symbol_group(symbol),
                    "asset_class": tools.gen_asset_class(symbol),
                    "timestamp": tick.index.values[-1],
                    "last": tools.to_decimal(tick['last'].values[-1]),
                    "lastsize": int(tick['lastsize'].values[-1]),
                    "bid": tools.to_decimal(tick['bid'].values[-1]),
                    "ask": tools.to_decimal(tick['ask'].values[-1]),
                    "bidsize": int(tick['bidsize'].values[-1]),
                    "asksize": int(tick['asksize'].values[-1]),
                    # "wap": kwargs['tick']['wap'],
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

    def on_quote_received(self, tickerId):
        try:

            symbol = self.ibConn.tickerSymbol(tickerId)

            if self.ibConn.contracts[tickerId].m_secType in ("OPT", "FOP"):
                quote = self.ibConn.optionsData[tickerId].to_dict(
                    orient='records')[0]
                quote['type'] = self.ibConn.contracts[tickerId].m_right
                quote['strike'] = tools.to_decimal(
                    self.ibConn.contracts[tickerId].m_strike)
                quote["symbol_group"] = self.ibConn.contracts[
                    tickerId].m_symbol + '_' + self.ibConn.contracts[
                        tickerId].m_secType
                quote = tools.mark_options_values(quote)
            else:
                quote = self.ibConn.marketData[tickerId].to_dict(
                    orient='records')[0]
                quote["symbol_group"] = tools.gen_symbol_group(symbol)

            quote["symbol"] = symbol
            quote["asset_class"] = tools.gen_asset_class(symbol)
            quote['bid'] = tools.to_decimal(quote['bid'])
            quote['ask'] = tools.to_decimal(quote['ask'])
            quote['last'] = tools.to_decimal(quote['last'])
            quote["kind"] = "QUOTE"

            # cash markets do not get RTVOLUME (handleTickString)
            if quote["asset_class"] == "CSH":
                quote['last'] = round(
                    float((quote['bid'] + quote['ask']) / 2), 5)
                quote['timestamp'] = datetime.utcnow(
                ).strftime("%Y-%m-%d %H:%M:%S.%f")

                # create synthetic tick
                if symbol in self.cash_ticks.keys() and \
                        quote['last'] != self.cash_ticks[symbol]:
                    self.on_tick_received(quote)
                else:
                    self.broadcast(quote, "QUOTE")

                self.cash_ticks[symbol] = quote['last']
            else:
                self.broadcast(quote, "QUOTE")

        except Exception:
            pass

    # -------------------------------------------

    def on_option_computation_received(self, tickerId):
        # try:
        symbol = self.ibConn.tickerSymbol(tickerId)

        tick = self.ibConn.optionsData[tickerId].to_dict(orient='records')[0]

        # must have values!
        for key in ('bid', 'ask', 'last', 'bidsize', 'asksize', 'lastsize',
                    'volume', 'delta', 'gamma', 'vega', 'theta'):
            if tick[key] == 0:
                return

        tick['type'] = self.ibConn.contracts[tickerId].m_right
        tick['strike'] = tools.to_decimal(
            self.ibConn.contracts[tickerId].m_strike)
        tick["symbol_group"] = self.ibConn.contracts[tickerId].m_symbol + \
            '_' + self.ibConn.contracts[tickerId].m_secType
        tick['volume'] = int(tick['volume'])
        tick['bid'] = tools.to_decimal(tick['bid'])
        tick['bidsize'] = int(tick['bidsize'])
        tick['ask'] = tools.to_decimal(tick['ask'])
        tick['asksize'] = int(tick['asksize'])
        tick['last'] = tools.to_decimal(tick['last'])
        tick['lastsize'] = int(tick['lastsize'])

        tick['price'] = tools.to_decimal(tick['price'], 2)
        tick['underlying'] = tools.to_decimal(tick['underlying'])
        tick['dividend'] = tools.to_decimal(tick['dividend'])
        tick['volume'] = int(tick['volume'])
        tick['iv'] = tools.to_decimal(tick['iv'])
        tick['oi'] = int(tick['oi'])
        tick['delta'] = tools.to_decimal(tick['delta'])
        tick['gamma'] = tools.to_decimal(tick['gamma'])
        tick['vega'] = tools.to_decimal(tick['vega'])
        tick['theta'] = tools.to_decimal(tick['theta'])

        tick["symbol"] = symbol
        tick["symbol_group"] = tools.gen_symbol_group(symbol)
        tick["asset_class"] = tools.gen_asset_class(symbol)

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
            tick['timestamp'] = datetime.utcnow().strftime(
                ibDataTypes['DATE_TIME_FORMAT_LONG_MILLISECS'])

        # treat as tick if last/volume changed
        if tick['last'] != prev_last or tick['lastsize'] != prev_lastsize:
            tick["kind"] = "TICK"
            self.on_tick_received(tick)

        # otherwise treat as quote
        else:
            tick["kind"] = "QUOTE"
            self.broadcast(tick, "QUOTE")

        # except Exception:
            # pass

    # -------------------------------------------

    def on_orderbook_received(self, tickerId):
        orderbook = self.ibConn.marketDepthData[tickerId].dropna(
            subset=['bid', 'ask']).fillna(0).to_dict(orient='list')

        # add symbol data to list
        symbol = self.ibConn.tickerSymbol(tickerId)
        orderbook['symbol'] = symbol
        orderbook["symbol_group"] = tools.gen_symbol_group(symbol)
        orderbook["asset_class"] = tools.gen_asset_class(symbol)
        orderbook["kind"] = "ORDERBOOK"

        # broadcast
        self.broadcast(orderbook, "ORDERBOOK")

    # -------------------------------------------
    def broadcast(self, data, kind):
        def int64_handler(o):
            if isinstance(o, np_int64):
                try:
                    return pd.to_datetime(o, unit='ms').strftime(
                        ibDataTypes["DATE_TIME_FORMAT_LONG"])
                except Exception:
                    return int(o)
            raise TypeError

        string2send = "%s %s" % (
            self.args["zmqtopic"], json.dumps(data, default=int64_handler))

        # print(kind, string2send)
        try:
            self.socket.send_string(string2send)
        except Exception:
            pass

    # -------------------------------------------
    def run(self):
        """Starts the blotter

        Connects to the TWS/GW, processes and logs market data,
        and broadcast it over TCP via ZeroMQ (which algo subscribe to)
        """

        self._check_unique_blotter()

        # initialize datastore
        if self.args["datastore"] is not None:
            datastore = "sql"
            if "pystore" in self.args["datastore"]:
                datastore = "pystore"
            datastore = tools.dynamic_import(
                "qtpylib.datastore.%s" % datastore, "Datastore")
            self.datastore = datastore(self.args["datastore"])

        self.zmq = zmq.Context(zmq.REP)
        self.socket = self.zmq.socket(zmq.PUB)
        self.socket.bind("tcp://*:" + str(self.args['zmqport']))

        db_modified = 0
        contracts = []
        prev_contracts = []
        first_run = True

        self.log_blotter.info("Connecting to Interactive Brokers...")
        self.ibConn = ezIBpy()
        self.ibConn.ibCallback = self.ibCallback

        while not self.ibConn.connected:
            self.ibConn.connect(clientId=int(self.args['ibclient']),
                                port=int(self.args['ibport']),
                                host=str(self.args['ibserver']),
                                account=self.args['ibaccount'])
            time.sleep(1)
            if not self.ibConn.connected:
                print('*', end="", flush=True)
        self.log_blotter.info("Connection established...")

        try:
            while True:

                if not os.path.exists(self.args['symbols']):
                    pd.DataFrame(columns=['symbol', 'sec_type',
                                          'exchange', 'currency', 'expiry',
                                          'strike', 'opt_type']).to_csv(
                                              self.args['symbols'],
                                              header=True, index=False)
                    tools.chmod(self.args['symbols'])
                else:
                    time.sleep(0.1)

                    # read db properties
                    db_data = os.stat(self.args['symbols'])
                    db_size = db_data.st_size
                    db_last_modified = db_data.st_mtime

                    # empty file
                    if db_size == 0:
                        if prev_contracts:
                            self.log_blotter.info('Cancel market data...')
                            self.ibConn.cancelMarketData()
                            time.sleep(0.1)
                            prev_contracts = []
                        continue

                    # modified?
                    if not first_run and db_last_modified == db_modified:
                        continue

                    # continue...
                    db_modified = db_last_modified

                    # read contructs db
                    df = pd.read_csv(self.args['symbols'], header=0)
                    if df.empty:
                        continue

                    # removed expired
                    now = datetime.now()
                    df = df[(
                        (df['expiry'] < 1e6) &
                        (df['expiry'] >= int(now.strftime('%Y%m')))
                    ) | (
                        (df['expiry'] >= 1e6) &
                        (df['expiry'] >= int(now.strftime('%Y%m%d')))
                    ) | np_isnan(df['expiry'])]

                    # fix expiry formatting (no floats)
                    df['expiry'] = df['expiry'].fillna(
                        0).astype(int).astype(str)
                    df.loc[df['expiry'] == "0", 'expiry'] = ""
                    df = df[df['sec_type'] != 'BAG']

                    df.fillna("", inplace=True)
                    df.to_csv(self.args['symbols'], header=True, index=False)
                    tools.chmod(self.args['symbols'])

                    # ignore commentee
                    df = df[~df['symbol'].str.contains("#")]
                    contracts = [tuple(x) for x in df.values]

                    if first_run:
                        first_run = False

                    else:
                        if contracts != prev_contracts:
                            # cancel market data for removed contracts
                            for cont in prev_contracts:
                                if cont not in contracts:
                                    contract = self.ibConn.createContract(cont)
                                    self.ibConn.cancelMarketData(contract)
                                    if self.args['orderbook']:
                                        self.ibConn.cancelMarketDepth(contract)
                                    time.sleep(0.1)
                                    cont_string = self.ibConn.contractString(
                                        cont).split('_')[0]
                                    self.log_blotter.info(
                                        'Contract Removed [%s]', cont_string)

                    # request market data
                    for contract in contracts:
                        if contract not in prev_contracts:
                            self.ibConn.requestMarketData(
                                self.ibConn.createContract(contract))
                            if self.args['orderbook']:
                                self.ibConn.requestMarketDepth(
                                    self.ibConn.createContract(contract))
                            time.sleep(0.1)
                            contract_string = self.ibConn.contractString(
                                contract).split('_')[0]
                            self.log_blotter.info(
                                'Contract Added [%s]', contract_string)

                    # update latest contracts
                    prev_contracts = contracts

                time.sleep(2)

        except (KeyboardInterrupt, SystemExit):
            self.quitting = True  # don't display connection errors on ctrl+c
            print("\n\n>>> Interrupted with Ctrl-c...")
            print("(waiting for running tasks to be completed)\n")
            sys.exit(1)

    # -------------------------------------------
    # CLIENT / STATIC
    # -------------------------------------------
    def history(self, symbols, start, end=None,
                resolution="1T", tz="UTC", continuous=True):
        """ get history from datastore """

        data = self.datastore.history(symbols=symbols, start=start, end=end,
                                      resolution=resolution, tz=tz,
                                      continuous=continuous)

        if data.empty:
            return data

        # setup dataframe
        return prepare_history(data=data, resolution=resolution,
                               tz=tz, continuous=continuous)

    # -------------------------------------------
    def stream(self, symbols="*", tick_handler=None, bar_handler=None,
               quote_handler=None, book_handler=None, tz="UTC"):

        # load runtime/default data
        if isinstance(symbols, str):
            symbols = symbols.split(',')
        symbols = list(map(str.strip, symbols))

        # connect to zeromq self.socket
        self.zmq = zmq.Context()
        sock = self.zmq.socket(zmq.SUB)
        sock.setsockopt_string(zmq.SUBSCRIBE, "")
        sock.connect('tcp://127.0.0.1:' + str(self.args['zmqport']))

        try:
            while True:
                message = sock.recv_string()

                if self.args["zmqtopic"] in message:
                    message = message.split(self.args["zmqtopic"])[1].strip()
                    data = json.loads(message)

                    if data['symbol'] not in symbols and "*" not in symbols:
                        continue

                    # convert None to np.nan !!
                    data.update((k, np_nan)
                                for k, v in data.items() if v is None)

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

                    try:
                        data["datetime"] = parse_date(data["timestamp"])
                    except Exception:
                        pass

                    df = pd.DataFrame(index=[0], data=data)
                    df.set_index('datetime', inplace=True)
                    df.index = pd.to_datetime(df.index, utc=True)
                    df.drop(["timestamp", "kind"], axis=1, inplace=True)

                    try:
                        df.index = df.index.tz_convert(tz)
                    except Exception:
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
            print("\n\n>>> Interrupted with Ctrl-c...")
            print("(waiting for running tasks to be completed)\n")
            print(".\n.\n.\n")
            sys.exit(1)

    # -------------------------------------------
    @staticmethod
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
                False: "won't backfill" / True: "backfilling, please wait"
        """

        data.sort_index(inplace=True)

        # currenly only supporting minute-data
        if resolution[-1] in ("K", "V"):
            self.backfilled = True
            return None

        # missing history?
        start_date = parse_date(start)
        end_date = parse_date(end) if end else datetime.utcnow()

        if data.empty:
            first_date = datetime.utcnow()
            last_date = datetime.utcnow()
        else:
            first_date = tools.datetime64_to_datetime(data.index.values[0])
            last_date = tools.datetime64_to_datetime(data.index.values[-1])

        ib_lookback = None
        if start_date < first_date:
            ib_lookback = tools.ib_duration_str(start_date)
        elif end_date > last_date:
            ib_lookback = tools.ib_duration_str(last_date)

        if not ib_lookback:
            self.backfilled = True
            return None

        self.backfill_resolution = "1 min" if resolution[-1] not in (
            "K", "V", "S") else "1 sec"
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
            time.sleep(0.1)

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


# ===========================================
# Utility functions --->
# ===========================================

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
        logger = tools.createLogger(__name__, logging.WARNING)

    tempdir = tempfile.gettempdir()

    # find specific name
    if blotter_name is not None:  # and blotter_name != 'auto-detect':
        args_cache_file = tempdir + "/" + blotter_name.lower() + ".qtpylib"
        if not os.path.exists(args_cache_file):
            logger.critical(
                "Cannot connect to running Blotter [%s]", blotter_name)
            if os.isatty(0):
                sys.exit(0)
            return []

    # no name provided - connect to last running
    else:
        blotter_files = sorted(glob.glob(tempdir + "/*.qtpylib"),
                               key=os.path.getmtime)

        if not blotter_files:
            logger.critical(
                "Cannot connect to running Blotter [%s]", blotter_name)
            if os.isatty(0):
                sys.exit(0)
            return []

        args_cache_file = blotter_files[-1]

    args = pickle.load(open(args_cache_file, "rb"))
    args['as_client'] = True

    return args

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
        all_dfs = [data[data['asset_class'] != 'FUT']]

        # generate dict of df per future
        futures_symbol_groups = list(
            data[data['asset_class'] == 'FUT']['symbol_group'].unique())
        for key in futures_symbol_groups:
            future_group = data[data['symbol_group'] == key]
            continuous = futures.create_continuous_contract(
                future_group, resolution)
            all_dfs.append(continuous)

        # make one df again
        # data = pd.concat(all_dfs, sort=True)
        data['datetime'] = data.index
        data.groupby([data.index, 'symbol'], as_index=False
                     ).last().set_index('datetime').dropna()

    data = tools.resample(data, resolution, tz)
    return data


# -------------------------------------------
if __name__ == "__main__":
    blotter = Blotter()
    blotter.run()
