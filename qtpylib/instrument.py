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

from qtpylib import futures
import math
from pandas import concat as pd_concat

class Instrument(str):
    """A string subclass that provides easy access to misc
    symbol-related methods and information.
    """

    # ---------------------------------------
    def _set_parent(self, parent):
        """ sets the parent object to communicate with """
        self.parent = parent

    # ---------------------------------------
    def _set_windows(self, ticks, bars):
        """ be aware of default windows """
        self.tick_window = ticks
        self.bar_window = bars

    # ---------------------------------------
    @staticmethod
    def _get_symbol_dataframe(df, symbol):
        try:
            # this produce a "IndexingError using Boolean Indexing" (on rare occasions)
            return df[ (df['symbol']==symbol) | (df['symbol_group']==symbol) ].copy()
        except:
            df = pd_concat([ df[df['symbol']==symbol], df[df['symbol_group']==symbol] ])
            df.loc[:, '_idx_'] = df.index
            return df.drop_duplicates(subset=['_idx_'], keep='last').drop('_idx_', axis=1)

    # ---------------------------------------
    def get_bars(self, lookback=None, as_dict=False):
        """ Get bars for this instrument

        :Parameters:
            lookback : int
                Max number of bars to get (None = all available bars)
            as_dict : bool
                Return a dict or a pd.DataFrame object

        :Retruns:
            bars : pd.DataFrame / dict
                The bars for this instruments
        """
        bars = self._get_symbol_dataframe(self.parent.bars, self)

        # add signal history to bars
        bars = self.parent._add_signal_history(df=bars, symbol=self)

        lookback = self.bar_window if lookback is None else lookback
        bars = bars[-lookback:]
        # if lookback is not None:
        #     bars = bars[-lookback:]

        if len(bars.index) > 0 and bars['asset_class'].values[-1] not in ("OPT", "FOP"):
            bars.drop(bars.columns[bars.columns.str.startswith('opt_')].tolist(), inplace=True, axis=1)

        if as_dict:
            bars.loc[:, 'datetime'] = bars.index
            bars = bars.to_dict(orient='records')
            if lookback == 1:
                bars = bars[0]

        return bars

    # ---------------------------------------
    def get_bar(self):
        """ Shortcut to self.get_bars(lookback=1, as_dict=True) """
        return self.get_bars(lookback=1, as_dict=True)

    # ---------------------------------------
    def get_ticks(self, lookback=None, as_dict=False):
        """ Get ticks for this instrument

        :Parameters:
            lookback : int
                Max number of ticks to get (None = all available ticks)
            as_dict : bool
                Return a dict or a pd.DataFrame object

        :Retruns:
            ticks : pd.DataFrame / dict
                The ticks for this instruments
        """
        ticks = self._get_symbol_dataframe(self.parent.ticks, self)

        lookback = self.tick_window if lookback is None else lookback
        ticks = ticks[-lookback:]
        # if lookback is not None:
        #     ticks = ticks[-lookback:]

        if len(ticks.index) > 0 and ticks['asset_class'].values[-1] not in ("OPT", "FOP"):
            ticks.drop(ticks.columns[ticks.columns.str.startswith('opt_')].tolist(), inplace=True, axis=1)

        if as_dict:
            ticks.loc[:, 'datetime'] = ticks.index
            ticks = ticks.to_dict(orient='records')
            if lookback == 1:
                ticks = ticks[0]

        return ticks

    # ---------------------------------------
    def get_tick(self):
        """ Shortcut to self.get_ticks(lookback=1, as_dict=True) """
        return self.get_ticks(lookback=1, as_dict=True)

    # ---------------------------------------
    def get_quote(self):
        """ Get last quote for this instrument

        :Retruns:
            quote : dict
                The quote for this instruments
        """
        if self in self.parent.quotes.keys():
            return self.parent.quotes[self]

    # ---------------------------------------
    def get_orderbook(self):
        """Get orderbook for the instrument

        :Retruns:
            orderbook : dict
                orderbook dict for the instrument
        """
        if self in self.parent.books.keys():
            return self.parent.books[self]

        return {
            "bid": [0], "bidsize": [0],
            "ask": [0], "asksize": [0]
        }

    # ---------------------------------------
    def order(self, direction, quantity, **kwargs):
        """ Send an order for this instrument

        :Parameters:

            direction : string
                Order Type (BUY/SELL, EXIT/FLATTEN)
            quantity : int
                Order quantity

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
        self.parent.order(direction.upper(), self, quantity, **kwargs)


    # ---------------------------------------
    def cancel_order(self, orderId):
        """ Cancels an order for this instrument

        :Parameters:
            orderId : int
                Order ID
        """

        self.parent.cancel_order(orderId)

    # ---------------------------------------
    def market_order(self, direction, quantity, **kwargs):
        """ Shortcut for ``instrument.order(...)`` and accepts all of its
        `optional parameters <#qtpylib.instrument.Instrument.order>`_

        :Parameters:
            direction : string
                Order Type (BUY/SELL, EXIT/FLATTEN)
            quantity : int
                Order quantity
        """
        kwargs['limit_price'] = 0
        kwargs['order_type'] = "MARKET"
        self.parent.order(direction.upper(), self, quantity=quantity, **kwargs)

    # ---------------------------------------
    def limit_order(self, direction, quantity, price, **kwargs):
        """ Shortcut for ``instrument.order(...)`` and accepts all of its
        `optional parameters <#qtpylib.instrument.Instrument.order>`_

        :Parameters:
            direction : string
                Order Type (BUY/SELL, EXIT/FLATTEN)
            quantity : int
                Order quantity
            price : float
                Limit price
        """
        kwargs['limit_price'] = price
        kwargs['order_type'] = "LIMIT"
        self.parent.order(direction.upper(), self, quantity=quantity, **kwargs)

    # ---------------------------------------
    def buy(self, quantity, **kwargs):
        """ Shortcut for ``instrument.order("BUY", ...)`` and accepts all of its
        `optional parameters <#qtpylib.instrument.Instrument.order>`_

        :Parameters:
            quantity : int
                Order quantity
        """
        self.parent.order("BUY", self, quantity=quantity, **kwargs)

    # ---------------------------------------
    def buy_market(self, quantity, **kwargs):
        """ Shortcut for ``instrument.order("BUY", ...)`` and accepts all of its
        `optional parameters <#qtpylib.instrument.Instrument.order>`_

        :Parameters:
            quantity : int
                Order quantity
        """
        kwargs['limit_price'] = 0
        kwargs['order_type'] = "MARKET"
        self.parent.order("BUY", self, quantity=quantity, **kwargs)

    # ---------------------------------------
    def buy_limit(self, quantity, price, **kwargs):
        """ Shortcut for ``instrument.order("BUY", ...)`` and accepts all of its
        `optional parameters <#qtpylib.instrument.Instrument.order>`_

        :Parameters:
            quantity : int
                Order quantity
            price : float
                Limit price
        """
        kwargs['limit_price'] = price
        kwargs['order_type'] = "LIMIT"
        self.parent.order("BUY", self, quantity=quantity, **kwargs)

    # ---------------------------------------
    def sell(self, quantity, **kwargs):
        """ Shortcut for ``instrument.order("SELL", ...)`` and accepts all of its
        `optional parameters <#qtpylib.instrument.Instrument.order>`_

        :Parameters:
            quantity : int
                Order quantity
        """
        self.parent.order("SELL", self, quantity=quantity, **kwargs)

    # ---------------------------------------
    def sell_market(self, quantity, **kwargs):
        """ Shortcut for ``instrument.order("SELL", ...)`` and accepts all of its
        `optional parameters <#qtpylib.instrument.Instrument.order>`_

        :Parameters:
            quantity : int
                Order quantity
        """
        kwargs['limit_price'] = 0
        kwargs['order_type'] = "MARKET"
        self.parent.order("SELL", self, quantity=quantity, **kwargs)

    # ---------------------------------------
    def sell_limit(self, quantity, price, **kwargs):
        """ Shortcut for ``instrument.order("SELL", ...)`` and accepts all of its
        `optional parameters <#qtpylib.instrument.Instrument.order>`_

        :Parameters:
            quantity : int
                Order quantity
            price : float
                Limit price
        """
        kwargs['limit_price'] = price
        kwargs['order_type'] = "LIMIT"
        self.parent.order("SELL", self, quantity=quantity, **kwargs)

    # ---------------------------------------
    def exit(self):
        """ Shortcut for ``instrument.order("EXIT", ...)``
        (accepts no parameters)"""
        self.parent.order("EXIT", self)

    # ---------------------------------------
    def flatten(self):
        """ Shortcut for ``instrument.order("FLATTEN", ...)``
        (accepts no parameters)"""
        self.parent.order("FLATTEN", self)

    # ---------------------------------------
    def get_contract(self):
        """Get contract object for this instrument

        :Retruns:
            contract : Object
                IB Contract object
        """
        return self.parent.get_contract(self)

    # ---------------------------------------
    def get_contract_details(self):
        """Get contract details for this instrument

        :Retruns:
            contract_details : dict
                IB Contract details
        """
        return self.parent.get_contract_details(self)

        # ---------------------------------------
    def get_tickerId(self):
        """Get contract's tickerId for this instrument

        :Retruns:
            tickerId : int
                IB Contract's tickerId
        """
        return self.parent.get_tickerId(self)

    # ---------------------------------------
    def get_positions(self, attr=None):
        """Get the positions data for the instrument

        :Optional:
            attr : string
                Position attribute to get
                (optional attributes: symbol, position, avgCost, account)

        :Retruns:
            positions : dict (positions) / float/str (attribute)
                positions data for the instrument
        """
        pos = self.parent.get_positions(self)
        try:
            if attr is not None:
                attr = attr.replace("quantity", "position")
            return pos[attr]
        except:
            return pos

    # ---------------------------------------
    def get_portfolio(self):
        """Get portfolio data for the instrument

        :Retruns:
            portfolio : dict
                portfolio data for the instrument
        """
        return self.parent.get_portfolio(self)

    # ---------------------------------------
    def get_orders(self):
        """Get orders for the instrument

        :Retruns:
            orders : list
                list of order data as dict
        """
        return self.parent.get_orders(self)

    # ---------------------------------------
    def get_pending_orders(self):
        """Get pending orders for the instrument

        :Retruns:
            orders : list
                list of pending order data as dict
        """
        return self.parent.get_pending_orders(self)


    # ---------------------------------------
    def get_active_order(self, order_type="STOP"):
        """Get artive order id for the instrument by order_type

        :Optional:
            order_type : string
                the type order to return: STOP (default), LIMIT, MARKET

        :Retruns:
            order : object
                IB Order object of instrument
        """
        return self.parent.active_order(self, order_type="STOP")


    # ---------------------------------------
    def get_trades(self):
        """Get orderbook for the instrument

        :Retruns:
            trades : pd.DataFrame
                instrument's trade log as DataFrame
        """
        return self.parent.get_trades(self)


    # ---------------------------------------
    def get_symbol(self):
        """Get symbol of this instrument

        :Retruns:
            symbol : string
                instrument's symbol
        """
        return self


    # ---------------------------------------
    def modify_order(self, orderId, quantity=None, limit_price=None):
        """Modify quantity and/or limit price of an active order for the instrument

        :Parameters:
            orderId : int
                the order id to modify

        :Optional:
            quantity : int
                the required quantity of the modified order
            limit_price : int
                the new limit price of the modified order
        """
        return self.parent.modify_order(self, orderId, quantity, limit_price)


    # ---------------------------------------
    def modify_order_group(self, orderId, entry=None, target=None, stop=None, quantity=None):
        """Modify bracket order

        :Parameters:
            orderId : int
                the order id to modify

        :Optional:
            entry: float
                new entry limit price (for unfilled limit orders only)
            target: float
                new target limit price (for unfilled limit orders only)
            stop: float
                new stop limit price (for unfilled limit orders only)
            quantity : int
                the required quantity of the modified order
        """
        return self.parent.modify_order_group(self, orderId=orderId,
            entry=entry, target=target, stop=stop, quantity=quantity)

    # ---------------------------------------
    def move_stoploss(self, stoploss):
        """Modify stop order. Auto-discover **orderId** and **quantity** and invokes ``self.modify_order(...)``.

        :Parameters:
            stoploss : float
                the new stoploss limit price

        """
        stopOrder = self.get_active_order(order_type="STOP")

        if stopOrder is not None and "orderId" in stopOrder.keys():
            self.modify_order(orderId=stopOrder['orderId'],
                quantity=stopOrder['quantity'], limit_price=stoploss)

    # ---------------------------------------
    def get_margin_requirement(self):
        """ Get margin requirements for intrument (futures only)

        :Retruns:
            margin : dict
                margin requirements for instrument (all values are ``None`` for non-futures instruments)
        """
        contract = self.get_contract()

        if contract.m_secType == "FUT":
            return futures.get_ib_futures(contract.m_symbol, contract.m_exchange)

        # else...
        return {
            "exchange": None,
            "symbol": None,
            "description": None,
            "class": None,
            "intraday_initial": None,
            "intraday_maintenance": None,
            "overnight_initial": None,
            "overnight_maintenance": None,
            "currency": None,
            "has_options": None
        }


    # ---------------------------------------
    def get_max_contracts_allowed(self, overnight=True):
        """ Get maximum contracts allowed to trade
        baed on required margin per contract and
        current account balance (futures only)

        :Parameters:
            overnight : bool
                Calculate based on Overnight margin (set to ``False`` to use Intraday margin req.)

        :Retruns:
            contracts : int
                maximum contracts allowed to trade (returns ``None`` for non-futures)
        """
        timeframe = 'overnight_initial' if overnight else 'intraday_initial'
        req_margin = self.get_margin_requirement()
        if req_margin[timeframe] is not None:
            if 'AvailableFunds' in self.parent.account:
                return int(math.floor(self.parent.account['AvailableFunds']/req_margin[timeframe]))

        return None

    def get_margin_max_contracts(self, overnight=True):
        """ Deprecated (renamed to ``get_max_contracts_allowed``)"""
        return self.get_max_contracts_allowed(overnight=overnight)

    # ---------------------------------------
    def get_ticksize(self, fallback=None):
        """ Get instrument ticksize

        :Parameters:
            fallback : flaot
                fallback ticksize (deprecated and ignored)

        :Retruns:
            ticksize : int
                Min. tick size
        """
        ticksize = self.parent.get_contract_details(self)['m_minTick']
        return float(ticksize)

    # ---------------------------------------
    def log_signal(self, signal):
        """ Log Signal for instrument

        :Parameters:
            signal : integer
                signal identifier (1, 0, -1)
        """
        return self.parent._log_signal(self, signal)

    # ---------------------------------------
    @property
    def bars(self):
        """(Property) Shortcut to self.get_bars()"""
        return self.get_bars()

    # ---------------------------------------
    @property
    def bar(self):
        """(Property) Shortcut to self.get_bar()"""
        return self.get_bar()

    # ---------------------------------------
    @property
    def ticks(self):
        """(Property) Shortcut to self.get_ticks()"""
        return self.get_ticks()

    # ---------------------------------------
    @property
    def tick(self):
        """(Property) Shortcut to self.get_tick()"""
        return self.get_tick()

    # ---------------------------------------
    @property
    def quote(self):
        """(Property) Shortcut to self.get_quote()"""
        return self.get_quote()

    # ---------------------------------------
    @property
    def orderbook(self):
        """(Property) Shortcut to self.get_orderbook()"""
        return self.get_orderbook()

    # ---------------------------------------
    @property
    def symbol(self):
        """(Property) Shortcut to self.get_symbol()"""
        return self

    # ---------------------------------------
    @property
    def contract(self):
        """(Property) Shortcut to self.get_contract()"""
        return self.get_contract()

    # ---------------------------------------
    @property
    def contract_details(self):
        """(Property) Shortcut to self.get_contract_details()"""
        return self.get_contract_details()

    # ---------------------------------------
    @property
    def tickerId(self):
        """(Property) Shortcut to self.get_tickerId()"""
        return self.get_tickerId()

    # ---------------------------------------
    @property
    def positions(self):
        """(Property) Shortcut to self.get_positions()"""
        return self.get_positions()

    # ---------------------------------------
    @property
    def position(self):
        """(Property) Shortcut to self.get_positions(position)"""
        return self.get_positions('position')

    # ---------------------------------------
    @property
    def portfolio(self):
        """(Property) Shortcut to self.get_portfolio()"""
        return self.get_portfolio()

    # ---------------------------------------
    @property
    def orders(self):
        """(Property) Shortcut to self.get_orders()"""
        return self.get_orders()

    # ---------------------------------------
    @property
    def pending_orders(self):
        """(Property) Shortcut to self.get_pending_orders()"""
        return self.get_pending_orders()

    # ---------------------------------------
    @property
    def trades(self):
        """(Property) Shortcut to self.get_trades()"""
        return self.get_trades()

    # ---------------------------------------
    @property
    def margin_requirement(self):
        """(Property) Shortcut to self.get_margin_requirement()"""
        return self.get_margin_requirement()

    # ---------------------------------------
    @property
    def margin_max_contracts(self):
        """ Deprecated (renamed to ``max_contracts_allowed``)"""
        return self.get_max_contracts_allowed()

    @property
    def max_contracts_allowed(self):
        """(Property) Shortcut to self.get_max_contracts_allowed()"""
        return self.get_max_contracts_allowed()

    # ---------------------------------------
    @property
    def ticksize(self):
        """(Property) Shortcut to self.get_ticksize()"""
        return self.get_ticksize()

