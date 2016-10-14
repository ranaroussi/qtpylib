#!/usr/bin/env python
# -*- coding: UTF-8 -*-
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

from numpy import isnan as isnan

from datetime import datetime
from dateutil.parser import parse as parse_date

from ezibpy import (
    ezIBpy, dataTypes as ibDataTypes
)

from qtpylib import (
    tools, path, futures
)

from decimal import *
getcontext().prec = 5

from abc import ABCMeta

# =============================================
logging.basicConfig(stream=sys.stdout, level=logging.INFO,
    format='%(asctime)s [%(levelname)s]: %(message)s')

# =============================================
def _gen_symbol_group(sym):
    sym = sym.strip()
    if "_FUT" in sym:
        sym = sym.split("_FUT")
        return sym[0][:-5]+"_F"
    elif "_CASH" in sym:
        return "CASH"
    return sym

def _gen_asset_class(sym):
    sym_class = str(sym).split("_")
    if len(sym_class) > 1:
        return sym_class[1].replace("CASH", "CSH")
    return "STK"


class Blotter():
    """Broker class initilizer

    :Optioanl:

        name : string
            name of the blotter (used by other modules)

        ** kwargs : mixed
            The names and values of the setting to set.
            (refer to the `Blotter Documentation <./blotter.html#available-arguments>`_)
            for full list of available parameters.
    """

    __metaclass__ = ABCMeta

    def __init__(self, name=None, **kwargs):

        # whats my name?
        self.name = str(self.__class__).split('.')[-1].split("'")[0].lower()
        if name is not None:
            self.name = name

        """ returns: running true/false """
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
        self.cash_ticks = {} # cache

        self.implicit_args = False

        # load args
        self.args_defaults = {
            "symbols": "symbols.csv",
            "ibport": "4001",
            "ibclient": "999",
            "ibserver": "localhost",
            "zmqport": "12345",
            "zmqtopic": "_qtpy_"+str(self.name.lower())+"_",
            "dbhost": "localhost",
            "dbport": "3306",
            "dbname": "qtpy",
            "dbuser": "root",
            "dbpass": ""
        }

        self.cahced_args     = {}
        self.args            = self.load_cli_args()
        self.duplicate_run   = False

        self.args_cache_file = tempfile.gettempdir()+"/"+self.name+".ezq"

        # read cached args
        if os.path.exists(self.args_cache_file):
            self.cahced_args = self._read_cached_args()

        if len(kwargs) > 0:
            self.set(**kwargs)

        # do stuff on exit
        atexit.register(self._on_exit)


    # -------------------------------------------
    def _on_exit(self):
        if "as_client" in self.args:
            return

        logging.info("Blotter stopped...")

        if self.ibConn is not None:
            logging.info("Cancel market data...")
            self.ibConn.cancelMarketData()

            logging.info("Disconnecting...")
            self.ibConn.disconnect()

        if not self.duplicate_run:
            logging.info("Deleting runtime args...")
            self._remove_cached_args()

        logging.info("Disconnecting from MySQL...")
        try:
            self.dbcurr.close()
            self.dbconn.close()
        except:
            pass

    # -------------------------------------------
    def _detect_running_blotter(self, name):
        return name

    # -------------------------------------------
    def _blotter_file_running(self):
        try:
            # not sure how this works on windows...
            command = 'pgrep -f '+ sys.argv[0]
            process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
            stdout_list = process.communicate()[0].decode('UTF-8').split("\n")
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
                print("REMOVING OLD TEMP")
                self._remove_cached_args()
            else:
                self.duplicate_run = True
                print("[ERROR]  Blotter is already running...")
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
        parser = argparse.ArgumentParser(description='ibBlotter')
        parser.add_argument('--symbols', default=self.args_defaults['symbols'],
            help='IB contracts CSV database (defaults ./symbols.csv)', required=False)
        parser.add_argument('--ibport', default=self.args_defaults['ibport'],
            help='TWS/IBGW Port to use (default: 4001)', required=False)
        parser.add_argument('--ibclient', default=self.args_defaults['ibclient'],
            help='TWS/IBGW Client ID (default: 999)', required=False)
        parser.add_argument('--ibserver', default=self.args_defaults['ibserver'],
            help='IB TWS/GW Server hostname (default: localhost)', required=False)
        parser.add_argument('--zmqport', default=self.args_defaults['zmqport'],
            help='ZeroMQ Port to use (default: 12345)', required=False)
        # parser.add_argument('--zmqtopic', default=self.args_defaults['zmqtopic'],
        #     help='Topic identifier for ZeroMQ (default: _qtpy_blottername_)', required=False)
        parser.add_argument('--dbhost', default=self.args_defaults['dbhost'],
            help='MySQL server hostname (default: localhost)', required=False)
        parser.add_argument('--dbport', default=self.args_defaults['dbport'],
            help='MySQL server port (default: 3306)', required=False)
        parser.add_argument('--dbname', default=self.args_defaults['dbname'],
            help='MySQL server database (default: qpy)', required=False)
        parser.add_argument('--dbuser', default=self.args_defaults['dbuser'],
            help='MySQL server username (default: root)', required=False)
        parser.add_argument('--dbpass', default=self.args_defaults['dbpass'],
            help='MySQL server password (default: none)', required=False)
        parser.add_argument('--dbskip', action='store_true',
            help='Skip MySQL logging (default: False)', required=False)

        args, unknown = parser.parse_known_args()

        # if no path, use same dir
        if args.symbols == "symbols.csv":
            args.symbols = path['caller']+'/'+args.symbols

        # hard-coded
        args.zmqtopic = self.args_defaults['zmqtopic']

        return args.__dict__

    # -------------------------------------------
    def set(self, **kwargs):
        self.implicit_args = True

        # load args
        set_args = {}
        for kw in kwargs:
            set_args[kw] = kwargs[kw]

        # override with cli args
        for arg in self.args:
            if arg not in set_args or (self.args[arg] != set_args[arg] and \
                self.args[arg] != self.args_defaults[arg]):
                set_args[arg] = self.args[arg]

        self.args = set_args

    # -------------------------------------------
    def ibCallback(self, caller, msg, **kwargs):
        if self.ibConn is None:
            return

        if caller == "handleConnectionClosed":
            logging.info("Lost conncetion to Interactive Brokers...")
            self._on_exit()
            self.run()

        elif caller == "handleTickString" and "tick" in kwargs:
            symbol = self.ibConn.tickerSymbol(msg.tickerId)
            data = {
                # available data from ib
                "symbol":       symbol,
                "symbol_group": _gen_symbol_group(symbol), # ES_F, ...
                "asset_class":  _gen_asset_class(symbol),
                "timestamp":    kwargs['tick']['time'],
                "last":         float(Decimal(kwargs['tick']['last'])),
                "lastsize":     int(kwargs['tick']['size']),
                "bid":          float(Decimal(kwargs['tick']['bid'])),
                "ask":          float(Decimal(kwargs['tick']['ask'])),
                "bidsize":      int(kwargs['tick']['bidsize']),
                "asksize":      int(kwargs['tick']['asksize']),
                # "wap":          kwargs['tick']['wap']
            }
            # print('.', end="", flush=True)
            self.on_tick_received(data)

        elif caller == "handleTickPrice" or caller == "handleTickSize":
            self.on_quote_received(msg.tickerId)

        # elif caller in "handleTickOptionComputation":
        #     self.on_option_received(msg.tickerId)

    # -------------------------------------------
    # def on_option_received(self, tickerId):
    #     try:
    #         symbol = self.ibConn.tickerSymbol(tickerId)
    #         quote  = self.ibConn.optionsData[tickerId].to_dict(orient='records')[0]
    #         quote['bid']  = float(Decimal(quote['bid']))
    #         quote['ask']  = float(Decimal(quote['ask']))
    #         quote['last'] = float(Decimal(quote['last']))
    #         quote["kind"] = "TICK"
    #         quote["symbol"] = symbol
    #         quote["symbol_group"] = _gen_symbol_group(symbol)
    #         quote["asset_class"]  = _gen_asset_class(symbol)

    #         self.broadcast(quote, "TICK")
    #     except:
    #         pass

    # -------------------------------------------
    def on_quote_received(self, tickerId):
        try:
            symbol = self.ibConn.tickerSymbol(tickerId)
            quote  = self.ibConn.marketData[tickerId].to_dict(orient='records')[0]
            quote['bid']  = float(Decimal(quote['bid']))
            quote['ask']  = float(Decimal(quote['ask']))
            quote['last'] = float(Decimal(quote['last']))
            quote["kind"] = "QUOTE"
            quote["symbol"] = symbol
            quote["symbol_group"] = _gen_symbol_group(symbol)
            quote["asset_class"]  = _gen_asset_class(symbol)

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
    def on_tick_received(self, tick):
        # data
        symbol    = tick['symbol']
        timestamp = datetime.strptime(tick['timestamp'],
            ibDataTypes["DATE_TIME_FORMAT_LONG_MILLISECS"])

        try:
            timestamp = parse_date(timestamp)
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
        self._raw_bars[symbol] = self._raw_bars[symbol].append(tick_data)

        # add tools.resampled raw to self._bars
        ohlc = self._raw_bars[symbol]['last'].resample('1T').ohlc()
        vol  = self._raw_bars[symbol]['volume'].resample('1T').sum()

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
            self._raw_bars[symbol].drop(self._raw_bars[symbol].index[:], inplace=True)

    # -------------------------------------------
    def broadcast(self, data, kind):
        string2send = "%s %s" % (self.args['zmqtopic'], json.dumps(data))
        # print(kind, string2send)
        try:
            self.socket.send_string(string2send)
        except:
            pass

    # -------------------------------------------
    def log2db(self, data, kind):
        if self.args['dbskip']:
            return

        symbol = data["symbol"].replace("_"+data["asset_class"], "")

        # set symbol id
        symbol_id = 0

        # in memory?
        if symbol in self.symbol_ids.keys():
            symbol_id = self.symbol_ids[symbol]

        # load from db
        else:
            sql = """SELECT id FROM `symbols` WHERE
                `symbol`=%s AND `symbol_group`=%s AND `asset_class`=%s LIMIT 1"""
            self.dbcurr.execute(sql, (symbol, data["symbol_group"], data["asset_class"]))
            row = self.dbcurr.fetchone()

            if row is not None:
                symbol_id = row[0]
            else:
                # save expiration (for building continous contracs)
                expiry = None
                if data["asset_class"] == "FUT":
                    try:
                        fut_symbol = symbol.split(data["symbol_group"].split('_')[0])[1]
                        date = datetime(int(fut_symbol[-4:]), ibDataTypes['MONTH_CODES'].index(fut_symbol[0]), 1)
                        day = 21 - (date.weekday() + 2) % 7
                        expiry = datetime(date.year, date.month, day).strftime("%Y-%m-%d")
                    except:
                        pass

                sql = """INSERT IGNORE INTO `symbols`
                    (`symbol`, `symbol_group`, `asset_class`, `expiry`) VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE `symbol`=`symbol`
                """

                self.dbcurr.execute(sql, (symbol, data["symbol_group"], data["asset_class"], expiry))
                try: self.dbconn.commit()
                except: return
                symbol_id = self.dbcurr.lastrowid

            # cache id
            self.symbol_ids[symbol] = symbol_id

        # gen epoch datetime
        if kind == "TICK":
            sql = """INSERT IGNORE INTO `ticks` (`datetime`, `symbol_id`, `bid`, `bidsize`,
                `ask`, `asksize`, `last`, `lastsize`) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE `symbol_id`=`symbol_id`
            """
            self.dbcurr.execute(sql, (data["timestamp"], symbol_id,
                float(data["bid"]), int(data["bidsize"]),
                float(data["ask"]), int(data["asksize"]),
                float(data["last"]), int(data["lastsize"])
            ))

        elif kind == "BAR":
            sql = """INSERT IGNORE INTO `bars`
                (`datetime`, `symbol_id`, `open`, `high`, `low`, `close`, `volume`)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE
                    `open`=%s, `high`=%s, `low`=%s, `close`=%s, `volume`=`volume`+%s
            """
            self.dbcurr.execute(sql, (data["timestamp"], symbol_id,
                float(data["open"]),float(data["high"]),float(data["low"]),float(data["close"]),int(data["volume"]),
                float(data["open"]),float(data["high"]),float(data["low"]),float(data["close"]),int(data["volume"])
            ))

        # commit
        try:
            self.dbconn.commit()
        except:
            pass

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

        logging.info("Connecting to Interactive Brokers...")
        self.ibConn = ezIBpy()
        self.ibConn.ibCallback = self.ibCallback

        while not self.ibConn.connected:
            self.ibConn.connect(clientId=int(self.args['ibclient']),
                port=int(self.args['ibport']), host=str(self.args['ibserver']))
            time.sleep(1)
            if not self.ibConn.connected:
                print('*', end="", flush=True)
        logging.info("Connection established...")

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
                            logging.info('Cancel market data...')
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
                        isnan(df['expiry'])
                    ]
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
                                    time.sleep(0.1)
                                    contract_string = self.ibConn.contractString(contract).split('_')[0]
                                    logging.info('Contract Removed ['+contract_string+']')

                    # request market data
                    for contract in contracts:
                        if contract not in prev_contracts:
                            self.ibConn.requestMarketData(self.ibConn.createContract(contract))
                            time.sleep(0.1)
                            contract_string = self.ibConn.contractString(contract).split('_')[0]
                            logging.info('Contract Added ['+contract_string+']')

                    # update latest contracts
                    prev_contracts = contracts

                time.sleep(2)


        except (KeyboardInterrupt, SystemExit):
            print("\n\n>>> Interrupted with Ctrl-c...")
            sys.exit(1)


    # -------------------------------------------
    # CLIENT / STATIC
    # -------------------------------------------
    def history(self, symbols, start, end=None, resolution="1T", tz="UTC"):
        # load runtime/default data
        if isinstance(symbols, str):
            symbols = symbols.split(',')

        # work with symbol groups
        symbols = list(map(_gen_symbol_group, symbols))

        # convert datetime to string for MySQL
        try: start = start.strftime(ibDataTypes["DATE_TIME_FORMAT_LONG_MILLISECS"])
        except: pass

        if end is not None:
            try: end = end.strftime(ibDataTypes["DATE_TIME_FORMAT_LONG_MILLISECS"])
            except: pass

        # connect to mysql
        self.mysql_connect()

        # --- build query
        table = 'ticks' if ("K" in resolution) | ("V" in resolution) | ("S" in resolution) else 'bars'

        query = """SELECT tbl.*,
            CONCAT(s.`symbol`, "_", s.`asset_class`) as symbol, s.symbol_group, s.asset_class, s.expiry
            FROM `{TABLE}` tbl LEFT JOIN `symbols` s ON tbl.symbol_id = s.id
            WHERE (`datetime` >= "{START}"{END_SQL}) """.replace(
            '{START}', start).replace('{TABLE}', table)

        if end is not None:
            query = query.replace('{END_SQL}', ' AND `datetime` <= "{END}"')
            query = query.replace('{END}', end)
        else:
            query = query.replace('{END_SQL}', '')

        if symbols[0].strip() != "*":
            query += """ AND ( s.`symbol_group` in ("{SYMBOLS}") OR s.`symbol` IN ("{SYMBOLS}") ) """
            query = query.replace('{SYMBOLS}', '","'.join(symbols))
        # --- end build query

        # get data using pandas
        data = pd.read_sql(query, self.dbconn).dropna()
        data.set_index('datetime', inplace=True)
        data.index = pd.to_datetime(data.index, utc=True)
        data['expiry'] = pd.to_datetime(data['expiry'], utc=True)


        if "K" not in resolution and "S" not in resolution:
            # construct continous contracts for futures
            all_dfs = [ data[data['asset_class']!='FUT'] ]

            # generate dict of df per future
            futures_symbol_groups = list( data[data['asset_class']=='FUT']['symbol_group'].unique() )
            for key in futures_symbol_groups:
                future_group = data[data['symbol_group']==key]
                continous = futures.create_continous_contract(future_group, resolution)
                all_dfs.append(continous)

            # make one df again
            data = pd.concat(all_dfs)

        data = tools.resample(data, resolution, tz)
        return data

    # -------------------------------------------
    def listen(self, symbols, tick_handler=None, bar_handler=None, quote_handler=None, tz="UTC"):
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

                if (self.args['zmqtopic'] in message):
                    message = message.split(self.args['zmqtopic'])[1].strip()
                    data    = json.loads(message)

                    if data['symbol'] not in symbols:
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

                    if data['kind'] == "TICK":
                        if tick_handler is not None:
                            tick_handler(df)
                    elif data['kind'] == "BAR":
                        if bar_handler is not None:
                            bar_handler(df)

        except (KeyboardInterrupt, SystemExit):
            print("\n\n>>> Interrupted with Ctrl-c...")
            sys.exit(1)

    # -------------------------------------------
    def drip(self, symbols, start, end=None, tick_handler=None, \
        bar_handler=None, resolution="1T", tz="UTC"):

        handler = None
        if ("K" in resolution or "V" in resolution) and tick_handler is not None:
            handler = tick_handler
        elif bar_handler is not None:
            handler = bar_handler
        else:
            return

        data = self.history(symbols, start=start, end=end, resolution=resolution, tz=tz)

        # stream
        try:
            while True:
                for index, _ in data.iterrows():
                    row = data[data.index==index]
                    handler(row)
                    time.sleep(2.5)

        except (KeyboardInterrupt, SystemExit):
            print("\n\n>>> Interrupted with Ctrl-c...")
            sys.exit(1)

    # -------------------------------------------
    def register(self, instruments):

        if isinstance(instruments, dict):
            instruments = list(instruments.values())

        if not isinstance(instruments, list):
            return

        db = pd.read_csv(self.args['symbols'], header=0).fillna("")

        instruments = pd.DataFrame(instruments)
        instruments.columns = db.columns

        db = db.append(instruments).drop_duplicates(keep="first")
        db.to_csv(self.args['symbols'], header=True, index=False)
        tools.chmod(self.args['symbols'])


    # -------------------------------------------
    def mysql_connect(self):
        if self.args['dbskip']:
            return

        if (self.dbcurr is None) & (self.dbconn is None):
            self.dbconn = pymysql.connect(
                host   = str(self.args['dbhost']),
                port   = int(self.args['dbport']),
                user   = str(self.args['dbuser']),
                passwd = str(self.args['dbpass']),
                db     = str(self.args['dbname'])
            )
            self.dbcurr = self.dbconn.cursor()

            # check for db schema
            self.dbcurr.execute("SHOW TABLES")
            tables = [ table[0] for table in self.dbcurr.fetchall() ]
            if "bars" in tables and \
                "ticks" in tables and \
                "symbols" in tables and \
                "trades" in tables:
                return

            # create database schema
            self.dbcurr.execute(open(path['library']+'/schema.sql', "rb" ).read())
            try:
                self.dbconn.commit()

                # unless we do this, there's a problem with curr.fetchX()
                self.dbcurr.close()
                self.dbconn.close()

                self.dbconn = pymysql.connect(
                    host   = str(self.args['dbhost']),
                    port   = int(self.args['dbport']),
                    user   = str(self.args['dbuser']),
                    passwd = str(self.args['dbpass']),
                    db     = str(self.args['dbname'])
                )
                self.dbcurr = self.dbconn.cursor()

            except:
                self.dbconn.rollback()
                print("[ERROR] Cannot create database schema")
                self._remove_cached_args()
                sys.exit(1)


# -------------------------------------------
if __name__ == "__main__":
    blotter = Blotter()
    blotter.run()