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

from qtpylib import futures
import math

class Instrument(str):
    """A string subclass that provides easy access to misc
    symbol-related methods and information.
    """

    # ---------------------------------------
    def _set_parent(self, parent):
        """ sets the parent object to communicate with """
        self.parent = parent


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
        bars = self.parent.bars[
            (self.parent.bars['symbol']==self) | (self.parent.bars['symbol_group']==self)
        ]

        # add signal history to bars
        bars = self.parent._add_signal_history(df=bars, symbol=self)

        if lookback is not None:
            bars = bars[-lookback:]

        if as_dict:
            bars['datetime'] = bars.index
            bars = bars.to_dict(orient='records')
            if lookback == 1:
                bars = bars[0]

        return bars

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
        ticks = self.parent.ticks[
            (self.parent.ticks['symbol']==self) | (self.parent.ticks['symbol_group']==self)
        ][-lookback:]

        if lookback is not None:
            ticks = ticks[-lookback:]

        if as_dict:
            ticks['datetime'] = ticks.index
            ticks = ticks.to_dict(orient='records')
            if lookback == 1:
                ticks = ticks[0]

        return ticks

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
            ticksize : float
                If using traling stop, pass the tick size for the instruments so you won't try to buy ES at 2200.128230 :)
            fillorkill: bool
                fill entire quantiry or none at all
            iceberg: bool
                is this an iceberg (hidden) order

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
        return self.parent.active_order_id(self)


    # ---------------------------------------
    def get_orderbook(self):
        """Get orderbook for the instrument

        :Retruns:
            orderbook : pd.DataFrame
                orderbook DataFrame for the instrument
        """
        return self.parent.get_orderbook(self)


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
    def get_margin_max_contracts(self, overnight=True):
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

    # ---------------------------------------
    def get_ticksize(self, fallback=0.01):
        """ Get instrument ticksize

        :Parameters:
            fallback : flaot
                fallback ticksize (used when cannot retrive data from exchange)

        """
        if hasattr(self, "ticksize_float"):
            return self.ticksize_float

        contract = self.get_contract()
        if contract.m_secType == "FUT":
            self.ticksize_float = futures.get_contract_ticksize(contract.m_symbol, fallback)
            return self.ticksize_float

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
    def orderbook(self):
        """(Property) Shortcut to self.get_orderbook()"""
        return self.get_orderbook()

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
        """(Property) Shortcut to self.get_margin_max_contracts()"""
        return self.get_margin_max_contracts()


    # ---------------------------------------
    @property
    def ticksize(self):
        """(Property) Shortcut to self.get_ticksize()"""
        return self.get_ticksize()

