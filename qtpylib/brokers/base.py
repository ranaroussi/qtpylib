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

import sys
import logging

from sqlalchemy import (
    create_engine, MetaData, ForeignKey,
    Table, Column, UniqueConstraint,
    Integer, Float, String, Date, DateTime,
    and_, text, insert
)
from sqlalchemy.dialects import mysql
from abc import ABCMeta, abstractmethod

import pandas as pd

from ezibpy import dataTypes as ibDataTypes

from qtpylib import (
    tools, asynctools
)

# =============================================
# check min, python version
if sys.version_info < (3, 4, *args, **kwargs):
    raise SystemError("QTPyLib requires Python version >= 3.4")

# =============================================
# Configure logging
tools.createLogger(__name__, logging.INFO)

# =============================================


class BaseBroker:

    __metaclass__ = ABCMeta

    def __init__(self, conn_str, debug=False, *args, **kwargs):
        self.prices = None

    def allocate(self, signals, max_funds=None,
                 max_weight=None, leverage=1, *args, **kwargs):

        if isinstance(signals, int):
            qty = pd.DataFrame(index=[0], columns=self.prices.columns)
            qty.loc[0, :] = 0
            return qty

        if not max_funds:
            max_funds = self.get_balance()

        weights = signals.div(signals.abs().sum(axis=1), axis=0).fillna(0)
        if max_weight:
            weights.where(weights < max_weight, max_weight, inplace=True)

        return leverage * np.floor((max_funds / weights) / self.prices)

    @abstractmethod
    def connect(self, *args, **kwargs):
        pass

    @abstractmethod
    def disconnect(self, *args, **kwargs):
        pass

    @abstractmethod
    def reconnect(self, *args, **kwargs):
        pass

    @abstractmethod
    def buy(self, qty_df, price_df, *args, **kwargs):
        pass

    @abstractmethod
    def buy_market(self, qty_df, *args, **kwargs):
        pass

    @abstractmethod
    def buy_moo(self, qty_df, *args, **kwargs):
        pass

    @abstractmethod
    def buy_moc(self, qty_df, *args, **kwargs):
        pass

    @abstractmethod
    def sell(self, qty_df, price_df, *args, **kwargs):
        pass

    @abstractmethod
    def sell_market(self, qty_df, *args, **kwargs):
        pass

    @abstractmethod
    def sell_moo(self, qty_df, *args, **kwargs):
        pass

    @abstractmethod
    def sell_moc(self, qty_df, *args, **kwargs):
        pass

    @abstractmethod
    def set_targets(self, targets_df, *args, **kwargs):
        pass

    @abstractmethod
    def set_stops(self, stops_df, *args, **kwargs):
        pass

    @abstractmethod
    def set_trailing_stops(self, triggers_df, offset_df,
                           kind="percent|bps|atr",
                           *args, **kwargs):
        pass

    @abstractmethod
    def set_orders_ttl(self, orderId, ttl, *args, **kwargs):
        pass

    @abstractmethod
    def cancel_order(self, orderId, *args, **kwargs):
        pass

    @abstractmethod
    def modify_order(self, orderId, dict, *args, **kwargs):
        pass

    @abstractmethod
    def close_positions(self, *args, **kwargs):
        pass

    @abstractmethod
    def get_positions(self, *args, **kwargs):
        pass

    @abstractmethod
    def get_portfolio(self, *args, **kwargs):
        pass

    @abstractmethod
    def get_balance(self, *args, **kwargs):
        pass

    @abstractmethod
    def get_orders(self, *args, **kwargs):
        pass

    @abstractmethod
    def get_account(self, *args, **kwargs):
        pass

    @abstractmethod
    def create_combination(self, *args, **kwargs):
        pass

    @abstractmethod
    def get_combination(self, *args, **kwargs):
        pass

    @abstractmethod
    def get_contract(self, *args, **kwargs):
        pass

    @abstractmethod
    def contract_details(self, *args, **kwargs):
        pass

    @abstractmethod
    def get_tickerId(self, *args, **kwargs):
        pass
