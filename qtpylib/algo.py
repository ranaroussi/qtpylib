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
import inspect
import pandas as pd
from numpy import nan
import sys
import logging
import os

from datetime import datetime

from qtpylib.broker import Broker
from qtpylib.instrument import Instrument
from qtpylib.workflow import validate_columns as validate_csv_columns
from qtpylib.blotter import prepare_history
from qtpylib import (
    tools, sms, asynctools
)

from abc import ABCMeta, abstractmethod

# =============================================
tools.createLogger(__name__)
# =============================================

class Algo(Broker):
    """Algo class initilizer (sub-class of Broker)

    :Parameters:

        instruments : list
            List of IB contract tuples
        resolution : str
            Desired bar resolution (using pandas resolution: 1T, 1H, etc). Use K for tick bars.
        tick_window : int
            Length of tick lookback window to keep. Defaults to 1
        bar_window : int
            Length of bar lookback window to keep. Defaults to 100
        timezone : str
            Convert IB timestamps to this timezone (eg. US/Central). Defaults to UTC
        preload : str
            Preload history when starting algo (using pandas resolution: 1H, 1D, etc). Use K for tick bars.
        continuous : bool
            Tells preloader to construct continuous Futures contracts (default is True)
        blotter : str
            Log trades to MySQL server used by this Blotter (default is "auto detect")
        sms: set
            List of numbers to text orders (default: None)
        log: str
            Path to store trade data (default: None)
        backtest: bool
            Whether to operate in Backtest mode (default: False)
        start: str
            Backtest start date (YYYY-MM-DD [HH:MM:SS[.MS]). Default is None
        end: str
            Backtest end date (YYYY-MM-DD [HH:MM:SS[.MS]). Default is None
        data : str
            Path to the directory with QTPyLib-compatible CSV files (for Backtesting using CSV files)
        output: str
            Path to save the recorded data (default: None)
        ibport: int
            IB TWS/GW Port to use (default: 4001)
        ibclient: int
            IB TWS/GW Client ID (default: 998)
        ibserver: str
            IB TWS/GW Server hostname (default: localhost)
    """

    __metaclass__ = ABCMeta

    def __init__(self, instruments, resolution,
        tick_window=1, bar_window=100, timezone="UTC", preload=None,
        continuous=True, blotter=None, sms=[], log=None, backtest=False,
        start=None, end=None, data=None, output=None,
        ibclient=998, ibport=4001, ibserver="localhost", **kwargs):

        # detect algo name
        self.name = str(self.__class__).split('.')[-1].split("'")[0]

        # initilize algo logger
        self.log_algo = logging.getLogger(__name__)

        # initilize strategy logger
        tools.createLogger(self.name)
        self.log = logging.getLogger(self.name)

        # override args with any (non-default) command-line args
        self.args = {arg: val for arg, val in locals().items() if arg not in ('__class__', 'self', 'kwargs')}
        self.args.update(kwargs)
        self.args.update(self.load_cli_args())

        # assign algo params
        self.bars           = pd.DataFrame()
        self.ticks          = pd.DataFrame()
        self.quotes         = {}
        self.books          = {}
        self.tick_count     = 0
        self.tick_bar_count = 0
        self.bar_count      = 0
        self.bar_hashes     = {}

        self.tick_window    = tick_window if tick_window > 0 else 1
        if "V" in resolution:
            self.tick_window = 1000
        self.bar_window     = bar_window if bar_window > 0 else 100
        self.resolution     = resolution.upper().replace("MIN", "T")
        self.timezone       = timezone
        self.preload        = preload
        self.continuous     = continuous

        self.backtest       = self.args["backtest"]
        self.backtest_start = self.args["start"]
        self.backtest_end   = self.args["end"]
        self.backtest_csv   = self.args["data"]

        # -----------------------------------
        self.sms_numbers    = self.args["sms"]
        self.trade_log_dir  = self.args["log"]
        self.blotter_name   = self.args["blotter"]
        self.record_output  = self.args["output"]

        # -----------------------------------
        # initiate broker/order manager
        super().__init__(instruments,
            **{arg: val for arg, val in self.args.items() if arg in (
                'ibport', 'ibclient', 'ibhost')})

        # -----------------------------------
        # signal collector
        self.signals = {}
        for sym in self.symbols:
            self.signals[sym] = pd.DataFrame()

        # -----------------------------------
        # initilize output file
        self.record_ts = None
        if self.record_output:
            self.datastore = tools.DataStore(self.args["output"])

        # ---------------------------------------
        # add stale ticks for more accurate time--based bars
        if not self.backtest and self.resolution[-1] not in ("K", "V"):
            self.bar_timer = asynctools.RecurringTask(
                self.add_stale_tick, interval_sec=1, init_sec=1, daemon=True)

        # ---------------------------------------
        # sanity checks for backtesting mode
        if self.backtest:
            if self.record_output is None:
                self.log_algo.error("Must provide an output file for Backtest mode")
                sys.exit(0)
            if self.backtest_start is None:
                self.log_algo.error("Must provide start date for Backtest mode")
                sys.exit(0)
            if self.backtest_end is None:
                self.backtest_end = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
            if self.backtest_csv is not None:
                if not os.path.exists(self.backtest_csv):
                    self.log_algo.error("CSV directory cannot be found (%s)" % self.backtest_csv)
                    sys.exit(0)
                elif self.backtest_csv.endswith("/"):
                    self.backtest_csv = self.backtest_csv[:-1]

        else:
            self.backtest_start = None
            self.backtest_end   = None
            self.backtest_csv   = None

    # ---------------------------------------
    def add_stale_tick(self):
        ticks = self.ticks.copy()
        if len(self.ticks.index) > 0:
            last_tick_sec = float(tools.datetime64_to_datetime(ticks.index.values[-1]).strftime('%M.%S'))

            for sym in list(self.ticks["symbol"].unique()):
                tick = ticks[ticks['symbol']==sym][-5:].to_dict(orient='records')[-1]
                tick['timestamp'] = datetime.utcnow()

                if last_tick_sec != float(tick['timestamp'].strftime("%M.%S")):
                    tick = pd.DataFrame(index=[0], data=tick)
                    tick.set_index('timestamp', inplace=True)
                    tick = tools.set_timezone(tick, tz=self.timezone)
                    tick.loc[:, 'ticksize'] = 0 # no real size

                    self._tick_handler(tick, stale_tick=True)


    # ---------------------------------------
    def load_cli_args(self):
        """
        Parse command line arguments and return only the non-default ones

        :Retruns: dict
            a dict of any non-default args passed on the command-line.
        """
        parser = argparse.ArgumentParser(description='QTPyLib Algo',
            formatter_class=argparse.ArgumentDefaultsHelpFormatter)

        parser.add_argument('--ibport', default=self.args["ibport"],
            help='IB TWS/GW Port', type=int)
        parser.add_argument('--ibclient', default=self.args["ibclient"],
            help='IB TWS/GW Client ID', type=int)
        parser.add_argument('--ibserver', default=self.args["ibserver"],
            help='IB TWS/GW Server hostname')
        parser.add_argument('--sms', default=self.args["sms"],
            help='Numbers to text orders', nargs='+')
        parser.add_argument('--log', default=self.args["log"],
            help='Path to store trade data')

        parser.add_argument('--backtest', default=self.args["backtest"],
            help='Work in Backtest mode (flag)', action='store_true')
        parser.add_argument('--start', default=self.args["start"],
            help='Backtest start date')
        parser.add_argument('--end', default=self.args["end"],
            help='Backtest end date')
        parser.add_argument('--data', default=self.args["data"],
            help='Path to backtester CSV files')
        parser.add_argument('--output', default=self.args["output"],
            help='Path to save the recorded data')

        parser.add_argument('--blotter',
            help='Log trades to this Blotter\'s MySQL')
        parser.add_argument('--continuous', default=self.args["continuous"],
            help='Construct continuous Futures contracts (flag)', action='store_true')

        # only return non-default cmd line args
        # (meaning only those actually given)
        cmd_args, unknown = parser.parse_known_args()
        args = {arg: val for arg, val in vars(cmd_args).items() if val != parser.get_default(arg)}
        return args

    # ---------------------------------------
    def run(self):
        """Starts the algo

        Connects to the Blotter, processes market data and passes
        tick data to the ``on_tick`` function and bar data to the
        ``on_bar`` methods.
        """

        history = pd.DataFrame()

        # get history from csv dir
        if self.backtest and self.backtest_csv:
            kind = "TICK" if self.resolution[-1] in ("K", "V") else "BAR"
            dfs = []
            for symbol in self.symbols:
                file = "%s/%s.%s.csv" % (self.backtest_csv, symbol, kind)
                if not os.path.exists(file):
                    self.log_algo.error("Can't load data for %s (%s doesn't exist)" % (symbol, file))
                    sys.exit(0)
                try:
                    df = pd.read_csv(file)

                    if "expiry" not in df.columns or not validate_csv_columns(df, kind, raise_errors=False):
                        self.log_algo.error("%s Doesn't appear to be a QTPyLib-compatible format" % file)
                        sys.exit(0)
                    if df['symbol'].values[-1] != symbol:
                        self.log_algo.error("%s Doesn't content data for %s" % (file, symbol))
                        sys.exit(0)
                    dfs.append(df)

                except:
                    self.log_algo.error("Error reading data for %s (%s)" % (symbol, file))
                    sys.exit(0)

            history = prepare_history(
                data       = pd.concat(dfs),
                resolution = self.resolution,
                tz         = self.timezone,
                continuous = self.continuous
            )
            history = history[history.index >= self.backtest_start]


        elif not self.blotter_args["dbskip"] and (self.backtest or self.preload):

            start = self.backtest_start if self.backtest else tools.backdate(self.preload)
            end = self.backtest_end if self.backtest else None

            history = self.blotter.history(
                symbols    = self.symbols,
                start      = start,
                end        = end,
                resolution = self.resolution,
                tz         = self.timezone,
                continuous = self.continuous
            )

            # history needs backfilling?
            # self.blotter.backfilled = True
            if not self.blotter.backfilled:
                # "loan" Blotter our ibConn
                self.blotter.ibConn = self.ibConn

                # call the back fill
                self.blotter.backfill(data=history, resolution=self.resolution, start=start, end=end)

                # re-get history from db
                history = self.blotter.history(
                    symbols    = self.symbols,
                    start      = start,
                    end        = end,
                    resolution = self.resolution,
                    tz         = self.timezone,
                    continuous = self.continuous
                )

                # take our ibConn back :)
                self.blotter.ibConn = None


        if self.backtest:
            # initiate strategy
            self.on_start()

            # drip history
            self.blotter.drip(history,
                self._tick_handler if self.resolution[-1] in ("K", "V") else self._bar_handler)

        else:
            # place history self.bars
            self.bars = history

            # add instruments to blotter in case they do not exist
            self.blotter.register(self.instruments)

            # initiate strategy
            self.on_start()

            # listen for RT data
            self.blotter.stream(
                symbols       = self.symbols,
                tz            = self.timezone,
                quote_handler = self._quote_handler,
                tick_handler  = self._tick_handler,
                bar_handler   = self._bar_handler,
                book_handler  = self._book_handler
            )

    # ---------------------------------------
    @abstractmethod
    def on_start(self):
        """
        Invoked once when algo starts. Used for when the strategy
        needs to initialize parameters upon starting.

        """
        # raise NotImplementedError("Should implement on_start()")
        pass

    # ---------------------------------------
    @abstractmethod
    def on_quote(self, instrument):
        """
        Invoked on every quote captured for the selected instrument.
        This is where you'll write your strategy logic for quote events.

        :Parameters:

            symbol : string
                `Instruments Object <#instrument-api>`_

        """
        # raise NotImplementedError("Should implement on_quote()")
        pass

    # ---------------------------------------
    @abstractmethod
    def on_tick(self, instrument):
        """
        Invoked on every tick captured for the selected instrument.
        This is where you'll write your strategy logic for tick events.

        :Parameters:

            symbol : string
                `Instruments Object <#instrument-api>`_

        """
        # raise NotImplementedError("Should implement on_tick()")
        pass

    # ---------------------------------------
    @abstractmethod
    def on_bar(self, instrument):
        """
        Invoked on every tick captured for the selected instrument.
        This is where you'll write your strategy logic for tick events.

        :Parameters:

            instrument : object
                `Instruments Object <#instrument-api>`_

        """
        # raise NotImplementedError("Should implement on_bar()")
        pass

    # ---------------------------------------
    @abstractmethod
    def on_orderbook(self, instrument):
        """
        Invoked on every change to the orderbook for the selected instrument.
        This is where you'll write your strategy logic for orderbook changes events.

        :Parameters:

            symbol : string
                `Instruments Object <#instrument-api>`_

        """
        # raise NotImplementedError("Should implement on_orderbook()")
        pass

    # ---------------------------------------
    @abstractmethod
    def on_fill(self, instrument, order):
        """
        Invoked on every order fill for the selected instrument.
        This is where you'll write your strategy logic for fill events.

        :Parameters:

            instrument : object
                `Instruments Object <#instrument-api>`_
            order : object
                Filled order data

        """
        # raise NotImplementedError("Should implement on_fill()")
        pass

    # ---------------------------------------
    def get_instrument(self, symbol):
        """
        A string subclass that provides easy access to misc
        symbol-related methods and information using shorthand.
        Refer to the `Instruments API <#instrument-api>`_
        for available methods and properties

        Call from within your strategy:
        ``instrument = self.get_instrument("SYMBOL")``

        :Parameters:

            symbol : string
                instrument symbol

        """
        instrument = Instrument(self._getsymbol_(symbol))
        instrument._set_parent(self)
        instrument._set_windows(ticks=self.tick_window, bars=self.bar_window)

        return instrument

    # ---------------------------------------
    def get_history(self, symbols, start, end=None, resolution="1T", tz="UTC"):
        """Get historical market data.
        Connects to Blotter and gets historical data from storage

        :Parameters:
            symbols : list
                List of symbols to fetch history for
            start : datetime / string
                History time period start date (datetime or YYYY-MM-DD[ HH:MM[:SS]] string)

        :Optional:
            end : datetime / string
                History time period end date (datetime or YYYY-MM-DD[ HH:MM[:SS]] string)
            resolution : string
                History resoluton (Pandas resample, defaults to 1T/1min)
            tz : string
                History timezone (defaults to UTC)

        :Returns:
            history : pd.DataFrame
                Pandas DataFrame object with historical data for all symbols
        """
        return self.blotter.history(symbols, start, end, resolution, tz)


    # ---------------------------------------
    # shortcuts to broker._create_order
    # ---------------------------------------
    def order(self, signal, symbol, quantity=0, **kwargs):
        """ Send an order for the selected instrument

        :Parameters:

            direction : string
                Order Type (BUY/SELL, EXIT/FLATTEN)
            symbol : string
                instrument symbol
            quantity : int
                Order quantiry

        :Optional:

            limit_price : float
                In case of a LIMIT order, this is the LIMIT PRICE
            expiry : int
                Cancel this order if not filled after *n* seconds (default 60 seconds)
            order_type : string
                Type of order: Market (default), LIMIT (default when limit_price is passed), MODIFY (required passing or orderId)
            orderId : int
                If modifying an order, the order id of the modified order
            target : float
                target (exit) price
            initial_stop : float
                price to set hard stop
            stop_limit: bool
                Flag to indicate if the stop should be STOP or STOP LIMIT (default False=STOP)
            trail_stop_at : float
                price at which to start trailing the stop
            trail_stop_by : float
                % of trailing stop distance from current price
            fillorkill: bool
                fill entire quantiry or none at all
            iceberg: bool
                is this an iceberg (hidden) order
            tif: str
                time in force (DAY, GTC, IOC, GTD). default is ``DAY``
        """
        self.log_algo.debug('ORDER: %s %4d %s %s', signal, quantity, symbol, kwargs)
        if signal.upper() == "EXIT" or signal.upper() == "FLATTEN":
            position = self.get_positions(symbol)
            if position['position'] == 0:
                return

            kwargs['symbol']    = symbol
            kwargs['quantity']  = abs(position['position'])
            kwargs['direction'] = "BUY" if position['position'] < 0 else "SELL"

            # print("EXIT", kwargs)

            try: self.record(position=0)
            except: pass

            if not self.backtest:
                self._create_order(**kwargs)

        else:
            if quantity == 0:
                return

            kwargs['symbol']    = symbol
            kwargs['quantity']  = abs(quantity)
            kwargs['direction'] = signal.upper()

            # print(signal.upper(), kwargs)

            # record
            try:
                quantity = -quantity if kwargs['direction'] == "BUY" else quantity
                self.record(position=quantity)
            except:
                pass

            if not self.backtest:
                self._create_order(**kwargs)


    # ---------------------------------------
    def cancel_order(self, orderId):
        """ Cancels a un-filled order

        Parameters:
            orderId : int
                Order ID
        """
        self._cancel_order(orderId)

    # ---------------------------------------
    def record(self, *args, **kwargs):
        """Records data for later analysis.
        Values will be logged to the file specified via
        ``--output [file]`` (along with bar data) as
        csv/pickle/h5 file.

        Call from within your strategy:
        ``self.record(key=value)``

        :Parameters:
            ** kwargs : mixed
                The names and values to record

        """
        if self.record_output:
            try: self.datastore.record(self.record_ts, *args, **kwargs)
            except: pass


    # ---------------------------------------
    def sms(self, text):
        """Sends an SMS message.
        Relies on properly setting up an SMS provider (refer to the
        SMS section of the documentation for more information about this)

        Call from within your strategy:
        ``self.sms("message text")``

        :Parameters:
            text : string
                The body of the SMS message to send

        """
        logging.info("SMS: "+str(text))
        sms.send_text(self.name +': '+ str(text), self.sms_numbers)

    # ---------------------------------------
    def _caller(self, caller):
        stack = [x[3] for x in inspect.stack()][1:-1]
        return caller in stack

    # ---------------------------------------
    @asynctools.multitasking.task
    def _book_handler(self, book):
        symbol = book['symbol']
        del book['symbol']
        del book['kind']

        self.books[symbol] = book
        self.on_orderbook(self.get_instrument(symbol))


    # ---------------------------------------
    @asynctools.multitasking.task
    def _quote_handler(self, quote):
        del quote['kind']
        self.quotes[quote['symbol']] = quote
        self.on_quote(self.get_instrument(quote))


    # ---------------------------------------
    @staticmethod
    def _get_window_per_symbol(df, window):
        # truncate tick window per symbol
        dfs = []
        for sym in list(df["symbol"].unique()):
            dfs.append(df[df['symbol']==sym][-window:])
        return pd.concat(dfs).sort_index()

    # ---------------------------------------
    @staticmethod
    def _thread_safe_merge(symbol, basedata, newdata):
        data = newdata
        if "symbol" in basedata.columns:
            data = pd.concat([basedata[basedata['symbol']!=symbol], data])

        data.loc[:, '_idx_'] = data.index
        data = data.drop_duplicates(subset=['_idx_','symbol','symbol_group','asset_class'], keep='last')
        data = data.drop('_idx_', axis=1)
        data = data.sort_index()

        try:
            return data.dropna(subset=['open', 'high', 'low', 'close', 'volume'])
        except:
            return data

    # ---------------------------------------
    @asynctools.multitasking.task
    def _tick_handler(self, tick, stale_tick=False):
        self._cancel_expired_pending_orders()

        # tick symbol
        symbol = tick['symbol'].values[0]
        self_ticks = self.ticks.copy() # work on copy

        # initial value
        if self.record_ts is None:
            self.record_ts = tick.index[0]

        if self.resolution[-1] not in ("S", "K", "V"):
            self_ticks = self._update_window(self_ticks, tick, window=self.tick_window)
            self.ticks = self._thread_safe_merge(symbol, self.ticks, self_ticks) # assign back
        else:
            self.ticks = self._update_window(self.ticks, tick)
            bars = tools.resample(self.ticks, self.resolution)

            if len(bars.index) > self.tick_bar_count > 0 or stale_tick:
                self.record_ts = tick.index[0]
                # self._bar_handler(bars, symbol)
                self._base_bar_handler(bars[bars['symbol']==symbol][-1:])

                window = int("".join([s for s in self.resolution if s.isdigit()]))
                # self.ticks = self.ticks[-window:]
                self_ticks = self._get_window_per_symbol(self_ticks, window)
                self.ticks = self._thread_safe_merge(symbol, self.ticks, self_ticks) # assign back

            self.tick_bar_count = len(bars.index)

            # record non time-based bars
            self.record(bars[-1:])

        if not stale_tick:
            self.on_tick(self.get_instrument(tick))

    # ---------------------------------------
    def _base_bar_handler(self, bar):
        """ non threaded bar handler (called by threaded _tick_handler) """
        # bar symbol
        symbol = bar['symbol'].values[0]
        self_bars = self.bars.copy() # work on copy

        is_tick_or_volume_bar = False
        handle_bar = True

        if self.resolution[-1] in ("K", "V"):
            is_tick_or_volume_bar = True
            handle_bar = self._caller("_tick_handler")

        # drip is also ok
        handle_bar = handle_bar or self._caller("drip")

        if is_tick_or_volume_bar:
            # just add a bar (used by tick bar bandler)
            self_bars = self._update_window(self_bars, bar, window=self.bar_window)
        else:
            # add the bar and resample to resolution
            self_bars = self._update_window(self_bars, bar, window=self.bar_window, resolution=self.resolution)

        # assign new data to self.bars
        self.bars = self._thread_safe_merge(symbol, self.bars, self_bars)

        # new bar?
        hash_string = bar[:1]['symbol'].to_string().translate(str.maketrans({key: None for key in "\n -:+"}))
        this_bar_hash = abs(hash(hash_string)) % (10 ** 8)

        newbar = True
        if symbol in self.bar_hashes.keys():
            newbar = self.bar_hashes[symbol] != this_bar_hash
        self.bar_hashes[symbol] = this_bar_hash

        if newbar and handle_bar:
            self.record_ts = bar.index[0]
            self.on_bar(self.get_instrument(symbol))

            # if self.resolution[-1] not in ("S", "K", "V"):
            self.record(bar)

    # ---------------------------------------
    @asynctools.multitasking.task
    def _bar_handler(self, bar):
        """ threaded version of _base_bar_handler (called by blotter's) """
        self._base_bar_handler(bar)


    # ---------------------------------------
    def _update_window(self, df, data, window=None, resolution=None):
        if df is None:
            df = data
        else:
            df = df.append(data)

        # resample
        if resolution is not None:
            try:
                tz = str(df.index.tz)
            except:
                tz = None
            df = tools.resample(df, resolution=resolution, tz=tz)

        # remove duplicates rows
        df.loc[:, '_idx_'] = df.index
        df.drop_duplicates(subset=['_idx_','symbol','symbol_group','asset_class'], keep='last', inplace=True)
        df.drop('_idx_', axis=1, inplace=True)

        # return
        if window is None:
            return df

        # return df[-window:]
        return self._get_window_per_symbol(df, window)

    # ---------------------------------------
    # signal logging methods
    # ---------------------------------------
    def _add_signal_history(self, df, symbol):
        """ Initilize signal history """
        if symbol not in self.signals.keys() or len(self.signals[symbol]) == 0:
            self.signals[symbol] = [nan]*len(df.index)
        else:
            self.signals[symbol].append(nan)

        self.signals[symbol] = self.signals[symbol][-len(df.index):]
        signal_count = len(self.signals[symbol])
        df.loc[-signal_count:, 'signal'] = self.signals[symbol][-signal_count:]

        return df

    def _log_signal(self, symbol, signal):
        """ Log signal

        :Parameters:
            symbol : string
                instruments symbol
            signal : integer
                signal identifier (1, 0, -1)

        """
        self.signals[symbol][-1] = signal
