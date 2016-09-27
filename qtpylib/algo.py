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
import inspect
import pandas as pd
from numpy import nan
import sys
import logging

from datetime import datetime

from qtpylib.blotter import Blotter
from qtpylib.broker import Broker
from qtpylib.instrument import Instrument
from qtpylib import (
    tools, sms
)

# =============================================
# parse args
parser = argparse.ArgumentParser(description='QTPy Algo Framework')
parser.add_argument('--ibport', default='4001', help='IB TWS/GW Port to use (default: 4001)', required=False)
parser.add_argument('--ibclient', default='998', help='IB TWS/GW Client ID (default: 998)', required=False)
parser.add_argument('--ibserver', default='localhost', help='IB TWS/GW Server hostname (default: localhost)', required=False)
parser.add_argument('--sms', nargs='+', help='Numbers to text orders', required=False)
parser.add_argument('--log', default=None, help='Path to store trade data (default: ~/qpy/trades/)', required=False)

parser.add_argument('--backtest', help='Work in Backtest mode', action='store_true', required=False)
parser.add_argument('--start', help='Backtest start date', required=False)
parser.add_argument('--end', help='Backtest end date', required=False)
parser.add_argument('--output', help='Path to save the recorded data', required=False)

parser.add_argument('--blotter', help='Log trades to the MySQL server used by this Blotter', required=False)

args, unknown = parser.parse_known_args()
# =============================================
#

from abc import ABCMeta, abstractmethod

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
        blotter : str
            Log trades to MySQL server used by this Blotter (default is "auto detect")

    """

    __metaclass__ = ABCMeta

    def __init__(self, instruments, resolution, \
        tick_window=1, bar_window=100, timezone="UTC", preload=None, \
        blotter=None, **kwargs):

        self.name = str(self.__class__).split('.')[-1].split("'")[0]

        # assign algo params
        self.bars           = pd.DataFrame()
        self.ticks          = pd.DataFrame()
        self.quotes         = {}
        self.tick_count     = 0
        self.tick_bar_count = 0
        self.bar_count      = 0
        self.bar_hash       = 0

        self.tick_window    = tick_window if tick_window > 0 else 1
        if "V" in resolution:
            self.tick_window = 1000
        self.bar_window     = bar_window if bar_window > 0 else 100
        self.resolution     = resolution.replace("MIN", "T")
        self.timezone       = timezone
        self.preload        = preload

        self.backtest       = args.backtest
        self.backtest_start = args.start
        self.backtest_end   = args.end

        # -----------------------------------
        self.sms_numbers    = [] if args.sms is None else args.sms
        self.trade_log_dir  = args.log
        self.blotter_name   = args.blotter if args.blotter is not None else blotter
        self.record_output  = args.output

        # -----------------------------------
        # load blotter settings && initilize Blotter
        self.load_blotter_args(args.blotter)
        self.blotter = Blotter(**self.blotter_args)

        # -----------------------------------
        # initiate broker/order manager
        super().__init__(instruments, ibclient=int(args.ibclient), \
            ibport=int(args.ibport), ibserver=str(args.ibserver))

        # -----------------------------------
        # signal collector
        self.signals = {}
        for sym in self.symbols:
            self.signals[sym] = pd.DataFrame()

        # -----------------------------------
        # initilize output file
        self.record_ts = None
        if self.record_output:
            self.datastore = tools.DataStore(args.output)

        # -----------------------------------
        # initiate strategy
        self.on_start()

    # ---------------------------------------
    def run(self):
        """Starts the algo

        Connects to the Blotter, processes market data and passes
        tick data to the ``on_tick`` function and bar data to the
        ``on_bar`` methods.
        """

        # -----------------------------------
        # backtest mode?
        if self.backtest:
            if self.output is None:
                print("ERROR: Must provide an output file for backtesting mode")
                sys.exit(0)
            if self.backtest_start is None:
                print("ERROR: Must provide start date for backtesting mode")
                sys.exit(0)
            if self.backtest_end is None:
                self.backtest_end = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')

            # backtest history
            self.blotter.drip(
                symbols       = self.symbols,
                start         = self.backtest_start,
                end           = self.backtest_end,
                resolution    = self.resolution,
                tz            = self.timezone,
                quote_handler = self._quote_handler,
                tick_handler  = self._tick_handler,
                bar_handler   = self._bar_handler
            )

        # -----------------------------------
        # live data mode
        else:
            # preload history
            if self.preload is not None:
                try: # dbskip may be active
                    self.bars = self.blotter.history(
                        symbols    = self.symbols,
                        start      = tools.backdate(self.preload),
                        resolution = self.resolution,
                        tz         = self.timezone
                    )
                except:
                    pass
                # print(self.bars)

            # add instruments to blotter in case they do not exist
            self.blotter.register(self.instruments)

            # listen for RT data
            self.blotter.listen(
                symbols       = self.symbols,
                tz            = self.timezone,
                quote_handler = self._quote_handler,
                tick_handler  = self._tick_handler,
                bar_handler   = self._bar_handler
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
            ticksize : float
                If using traling stop, pass the tick size for the instruments so you won't try to buy ES at 2200.128230 :)
            fillorkill: bool
                fill entire quantiry or none at all
            iceberg: bool
                is this an iceberg (hidden) order
        """
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
            self.datastore.record(self.record_ts, *args, **kwargs)


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
    def _quote_handler(self, quote):
        # self._cancel_expired_pending_orders()
        self.quotes[quote['symbol']] = quote
        self.on_quote(self.get_instrument(quote))

    # ---------------------------------------
    def _tick_handler(self, tick):
        self._cancel_expired_pending_orders()

        if "K" not in self.resolution and "V" not in self.resolution:
            self.ticks = self._update_window(self.ticks, tick, window=self.tick_window)
        else:
            self.ticks = self._update_window(self.ticks, tick)
            bar = tools.resample(self.ticks, self.resolution)
            if len(bar.index) > self.tick_bar_count > 0:
                self.record_ts = tick.index[0]
                self._bar_handler(bar)

                periods = int("".join([s for s in self.resolution if s.isdigit()]))
                self.ticks = self.ticks[-periods:]

            self.tick_bar_count = len(bar)

            # record tick bar
            self.record(bar)

        self.on_tick(self.get_instrument(tick))


    # ---------------------------------------
    def _bar_handler(self, bar):

        is_tick_or_volume_bar = False
        handle_bar  = True

        if "K" in self.resolution or "V" in self.resolution:
            is_tick_or_volume_bar = True
            handle_bar = self._caller("_tick_handler")

        if is_tick_or_volume_bar:
            # just add a bar (used by tick bar bandler)
            self.bars = self._update_window(self.bars, bar, window=self.bar_window)
        else:
            # add the bar and resample to resolution
            self.bars = self._update_window(self.bars, bar, window=self.bar_window, resolution=self.resolution)

        # new bar?
        this_bar_hash = abs(hash(str(self.bars.index.values[-1]))) % (10 ** 8)
        newbar = (self.bar_hash != this_bar_hash)
        self.bar_hash = this_bar_hash

        if newbar & handle_bar:
            self.record_ts = bar.index[0]
            self.on_bar(self.get_instrument(bar))

            if "K" not in self.resolution and "V" not in self.resolution:
                self.record(bar)


    # ---------------------------------------
    def _update_window(self, df, data, window=None, resolution=None):
        if df is None:
            df = data
        else:
            df = df.append(data)

        if resolution is not None:
            try:
                tz = str(df.index.tz)
            except:
                tz = None
            df = tools.resample(df, resolution=resolution, tz=tz)

        if window is None:
            return df

        return df[-window:]

    # ---------------------------------------
    # signal logging methods
    # ---------------------------------------
    def _add_signal_history(self, df, symbol):
        """ Initilize signal history """
        if symbol not in self.signals.keys() or len(self.signals[symbol]) == 0:
            self.signals[symbol] = [nan]*len(df)
        else:
            self.signals[symbol].append(nan)

        self.signals[symbol] = self.signals[symbol][-len(df):]
        df.loc[-len(self.signals[symbol]):, 'signal'] = self.signals[symbol]

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