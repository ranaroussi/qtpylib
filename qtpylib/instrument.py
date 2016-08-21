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

        if lookback is not None:
            bars = bars[-lookback:]

        if as_dict:
            bars.loc[:, 'datetime'] = bars.index
            bars = bars.to_dict(orient='records')

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
            bars : pd.DataFrame / dict
                The ticks for this instruments
        """
        ticks = self.parent.ticks[
            (self.parent.ticks['symbol']==self) | (self.parent.ticks['symbol_group']==self)
        ][-lookback:]

        if lookback is not None:
            ticks = ticks[-lookback:]

        if as_dict:
            ticks.loc[:, 'datetime'] = ticks.index
            ticks = ticks.to_dict(orient='records')

        return ticks

    # ---------------------------------------
    def order(self, direction, quantity, **kwargs):
        """ Send an order for this instrument

        :Parameters:

            direction : string
                Order Type (BUY/SELL, EXIT/FLATTEN)
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
            trail_stop_at : float
                price at which to start trailing the stop
            trail_stop_by : float
                % of trailing stop distance from current price
            ticksize : float
                If using traling stop, pass the tick size for the instruments so you won't try to buy ES at 2200.128230 :)

        """
        self.parent.order(direction.upper(), self, quantity, **kwargs)

    # ---------------------------------------
    def buy(self, quantity, **kwargs):
        """ Shortcut for ``self.order("BUY", ...)`` `(ref) <#qtpylib.instrument.Instrument.order>`_ """
        self.parent.order("BUY", self, quantity, **kwargs)

    # ---------------------------------------
    def sell(self, quantity, **kwargs):
        """ Shortcut for ``self.order("SELL", ...)`` `(ref) <#qtpylib.instrument.Instrument.order>`_ """
        self.parent.order("SELL", self, quantity, **kwargs)

    # ---------------------------------------
    def exit(self, **kwargs):
        """ Shortcut for ``self.order("EXIT", ...)`` `(ref) <#qtpylib.instrument.Instrument.order>`_ """
        self.parent.order("EXIT", self, quantity=0, **kwargs)

    # ---------------------------------------
    def flatten(self, **kwargs):
        """ Shortcut for ``self.order("FLATTEN", ...)`` `(ref) <#qtpylib.instrument.Instrument.order>`_ """
        self.parent.order("FLATTEN", self, quantity=0, **kwargs)

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
            return pos[attr]
        except:
            return pos

    # ---------------------------------------
    def get_portfolio(self):
        """Get portfolio data for the instrument

        :Retruns:
            contract : dict
                portfolio data for the instrument
        """
        return self.parent.get_portfolio(self)

    # ---------------------------------------
    def get_orders(self):
        """Get orders for the instrument

        :Retruns:
            contract : list
                list of order data as dict
        """
        return self.parent.get_orders(self)

    # ---------------------------------------
    def get_pending_orders(self):
        """Get pending orders for the instrument

        :Retruns:
            contract : list
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
            contract : object
                IB Order object of instrument
        """
        return self.parent.active_order_id(self)


    # ---------------------------------------
    def get_orderbook(self):
        """Get orderbook for the instrument

        :Retruns:
            contract : pd.DataFrame
                orderbook DataFrame for the instrument
        """
        return self.parent.get_orderbook(self)


    # ---------------------------------------
    def get_symbol(self):
        """Get symbol of this instrument

        :Retruns:
            contract : pd.DataFrame
                orderbook DataFrame for the instrument
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

