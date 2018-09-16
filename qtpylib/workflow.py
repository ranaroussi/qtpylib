#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# QTPyLib: Quantitative Trading Python Library
# https://github.com/ranaroussi/qtpylib
#
# Copyright 2016-2018 Ran Aroussi
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

import logging
import time
import sys

import numpy as np
import pandas as pd

import pymysql
from pymysql.constants.CLIENT import MULTI_STATEMENTS

from ezibpy import ezIBpy
from ezibpy.utils import contract_expiry_from_symbol

from qtpylib import tools
from qtpylib.blotter import (
    load_blotter_args, get_symbol_id,
    mysql_insert_tick, mysql_insert_bar
)

_IB_HISTORY_DOWNLOADED = False

# =============================================
# check min, python version
if sys.version_info < (3, 4):
    raise SystemError("QTPyLib requires Python version >= 3.4")

# =============================================
tools.createLogger(__name__)  # .setLevel(logging.DEBUG)
# =============================================


def ibCallback(caller, msg, **kwargs):
    global _IB_HISTORY_DOWNLOADED
    if caller == "handleHistoricalData":
        if kwargs["completed"]:
            _IB_HISTORY_DOWNLOADED = True
        # print(kwargs)


def get_data_ib(instrument, start, resolution="1 min",
                blotter=None, output_path=None):
    """
    Downloads historical data from Interactive Brokers

    :Parameters:
        instrument : mixed
            IB contract tuple / string (same as that given to strategy)
        start : str
            Backtest start date (YYYY-MM-DD [HH:MM:SS[.MS])

    :Optional:
        resolution : str
            1/5/15/30 secs, 1/2/3/5/15/30 min (default 1min), 1 hour, 1 day
        blotter : str
            Store MySQL server used by this Blotter (default is "auto detect")
        output_path : str
            Path to where the resulting CSV should be saved (optional)

    :Returns:
        data : pd.DataFrame
            Pandas DataFrame in a QTPyLib-compatible format and timezone
    """
    global _IB_HISTORY_DOWNLOADED
    _IB_HISTORY_DOWNLOADED = False

    # load blotter settings
    blotter_args = load_blotter_args(
        blotter, logger=logging.getLogger(__name__))

    # create contract string (no need for connection)
    ibConn = ezIBpy()
    ibConn.ibCallback = ibCallback

    if not ibConn.connected:
        ibConn.connect(clientId=997,
                       port=int(blotter_args['ibport']),
                       host=str(blotter_args['ibserver']))

    # generate a valid ib tuple
    instrument = tools.create_ib_tuple(instrument)
    contract_string = ibConn.contractString(instrument)
    contract = ibConn.createContract(instrument)

    ibConn.requestHistoricalData(contracts=[contract],
                                 data="TRADES", resolution=resolution,
                                 lookback=tools.ib_duration_str(start),
                                 rth=False)

    while not _IB_HISTORY_DOWNLOADED:
        time.sleep(1)

    ibConn.disconnect()

    data = ibConn.historicalData[contract_string]
    data['datetime'] = data.index
    return prepare_data(instrument, data, output_path=output_path)


# =============================================
# data preparation methods
# =============================================

_BARS_COLSMAP = {
    'open': 'open',
    'high': 'high',
    'low': 'low',
    'close': 'close',
    'volume': 'volume',
    'opt_price': 'opt_price',
    'opt_underlying': 'opt_underlying',
    'opt_dividend': 'opt_dividend',
    'opt_volume': 'opt_volume',
    'opt_iv': 'opt_iv',
    'opt_oi': 'opt_oi',
    'opt_delta': 'opt_delta',
    'opt_gamma': 'opt_gamma',
    'opt_vega': 'opt_vega',
    'opt_theta': 'opt_theta'
}
_TICKS_COLSMAP = {
    'bid': 'bid',
    'bidsize': 'bidsize',
    'ask': 'ask',
    'asksize': 'asksize',
    'last': 'last',
    'lastsize': 'lastsize',
    'opt_price': 'opt_price',
    'opt_underlying': 'opt_underlying',
    'opt_dividend': 'opt_dividend',
    'opt_volume': 'opt_volume',
    'opt_iv': 'opt_iv',
    'opt_oi': 'opt_oi',
    'opt_delta': 'opt_delta',
    'opt_gamma': 'opt_gamma',
    'opt_vega': 'opt_vega',
    'opt_theta': 'opt_theta'
}

# ---------------------------------------------


def validate_columns(df, kind="BAR", raise_errors=True):
    global _TICKS_COLSMAP, _BARS_COLSMAP
    # validate columns
    if "asset_class" not in df.columns:
        if raise_errors:
            raise ValueError('Column asset_class not found')
        return False

    is_option = "OPT" in list(df['asset_class'].unique())

    colsmap = _TICKS_COLSMAP if kind == "TICK" else _BARS_COLSMAP

    for el in colsmap:
        col = colsmap[el]
        if col not in df.columns:
            if "opt_" in col and is_option:
                if raise_errors:
                    raise ValueError('Column %s not found' % el)
                return False
            elif "opt_" not in col and not is_option:
                if raise_errors:
                    raise ValueError('Column %s not found' % el)
                return False
    return True

# ---------------------------------------------


def prepare_data(instrument, data, output_path=None,
                 index=None, colsmap=None, kind="BAR", resample="1T"):
    """
    Converts given DataFrame to a QTPyLib-compatible format and timezone

    :Parameters:
        instrument : mixed
            IB contract tuple / string (same as that given to strategy)
        data : pd.DataFrame
            Pandas DataDrame with that instrument's market data
        output_path : str
            Path to where the resulting CSV should be saved (optional)
        index : pd.Series
            Pandas Series that will be used for df's index (optioanl)
        colsmap : dict
            Dict for mapping df's columns to those used by QTPyLib
            (default assumes same naming convention as QTPyLib's)
        kind : str
            Is this ``BAR`` or ``TICK`` data
        resample : str
            Pandas resolution (defaults to 1min/1T)

    :Returns:
        data : pd.DataFrame
            Pandas DataFrame in a QTPyLib-compatible format and timezone
    """

    global _TICKS_COLSMAP, _BARS_COLSMAP

    # work on copy
    df = data.copy()

    # ezibpy's csv?
    if set(df.columns) == set([
            'datetime', 'C', 'H', 'L', 'O', 'OI', 'V', 'WAP']):
        df.rename(columns={
            'datetime': 'datetime',
            'O': 'open',
            'H': 'high',
            'L': 'low',
            'C': 'close',
            'OI': 'volume',
        }, inplace=True)
        df.index = pd.to_datetime(df['datetime'])
        df.index = df.index.tz_localize(tools.get_timezone()).tz_convert("UTC")
        index = None

    # lower case columns
    df.columns = map(str.lower, df.columns)

    # set index
    if index is None:
        index = df.index

    # set defaults columns
    if not isinstance(colsmap, dict):
        colsmap = {}

    _colsmap = _TICKS_COLSMAP if kind == "TICK" else _BARS_COLSMAP
    for el in _colsmap:
        if el not in colsmap:
            colsmap[el] = _colsmap[el]

    # generate a valid ib tuple
    instrument = tools.create_ib_tuple(instrument)

    # create contract string (no need for connection)
    ibConn = ezIBpy()
    contract_string = ibConn.contractString(instrument)
    asset_class = tools.gen_asset_class(contract_string)
    symbol_group = tools.gen_symbol_group(contract_string)

    # add symbol data
    df.loc[:, 'symbol'] = contract_string
    df.loc[:, 'symbol_group'] = symbol_group
    df.loc[:, 'asset_class'] = asset_class

    # validate columns
    valid_cols = validate_columns(df, kind)
    if not valid_cols:
        raise ValueError('Invalid Column list')

    # rename columns to map
    df.rename(columns=colsmap, inplace=True)

    # force option columns on options
    if asset_class == "OPT":
        df = tools.force_options_columns(df)

    # remove all other columns
    known_cols = list(colsmap.values()) + \
        ['symbol', 'symbol_group', 'asset_class', 'expiry']
    for col in df.columns:
        if col not in known_cols:
            df.drop(col, axis=1, inplace=True)

    # set UTC index
    df.index = pd.to_datetime(index)
    df = tools.set_timezone(df, "UTC")
    df.index.rename("datetime", inplace=True)

    # resample
    if resample and kind == "BAR":
        df = tools.resample(df, resolution=resample, tz="UTC")

    # add expiry
    df.loc[:, 'expiry'] = np.nan
    if asset_class in ("FUT", "OPT", "FOP"):
        df.loc[:, 'expiry'] = contract_expiry_from_symbol(contract_string)

    # save csv
    if output_path is not None:
        output_path = output_path[
            :-1] if output_path.endswith('/') else output_path
        df.to_csv("%s/%s.%s.csv" % (output_path, contract_string, kind))

    # return df
    return df

# ---------------------------------------------


def store_data(df, blotter=None, kind="BAR"):
    """
    Store QTPyLib-compatible csv files in Blotter's MySQL.
    TWS/GW data are required for determining futures/options expiration

    :Parameters:
        df : dict
            Tick/Bar data

    :Optional:
        blotter : str
            Store MySQL server used by this Blotter (default is "auto detect")
        kind : str
            Is this ``BAR`` or ``TICK`` data
    """

    # validate columns
    valid_cols = validate_columns(df, kind)
    if not valid_cols:
        raise ValueError('Invalid Column list')

    # load blotter settings
    blotter_args = load_blotter_args(
        blotter, logger=logging.getLogger(__name__))

    # blotter not running
    if blotter_args is None:
        raise Exception("Cannot connect to running Blotter.")

    # cannot continue
    if blotter_args['dbskip']:
        raise Exception("Cannot continue. Blotter running with --dbskip")

    # connect to mysql using blotter's settings
    dbconn = pymysql.connect(
        client_flag=MULTI_STATEMENTS,
        host=str(blotter_args['dbhost']),
        port=int(blotter_args['dbport']),
        user=str(blotter_args['dbuser']),
        passwd=str(blotter_args['dbpass']),
        db=str(blotter_args['dbname']),
        autocommit=True
    )
    dbcurr = dbconn.cursor()

    # loop through symbols and save in db
    for symbol in list(df['symbol'].unique()):
        data = df[df['symbol'] == symbol]
        symbol_id = get_symbol_id(symbol, dbconn, dbcurr)

        # prepare columns for insert
        data.loc[:, 'timestamp'] = data.index.strftime('%Y-%m-%d %H:%M:%S')
        data.loc[:, 'symbol_id'] = symbol_id

        # insert row by row to handle greeks
        data = data.to_dict(orient="records")

        if kind == "BAR":
            for _, row in enumerate(data):
                mysql_insert_bar(row, symbol_id, dbcurr)
        else:
            for _, row in enumerate(data):
                mysql_insert_tick(row, symbol_id, dbcurr)

        try:
            dbconn.commit()
        except Exception as e:
            return False

    return True


# =============================================
# data analyze methods
# =============================================

def analyze_portfolio(file):
    """ analyze portfolio (TBD) """
    pass
