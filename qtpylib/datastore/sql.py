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

import pandas as pd

from ezibpy import dataTypes as ibDataTypes

from qtpylib import (
    tools, asynctools
)

# =============================================
# check min, python version
if sys.version_info < (3, 4):
    raise SystemError("QTPyLib requires Python version >= 3.4")

# =============================================
# Configure logging
tools.createLogger(__name__, logging.INFO)

# =============================================


class Datastore():

    def __init__(self, conn_str, debug=False, **kwargs):
        """ initialize engine """

        # parse conn_str
        dbname = conn_str.strip().split('/')[-1]
        conn_str = conn_str.replace("/%s" % dbname, "")
        self.dialect = conn_str.split('://')[0].split('+')[0].lower()

        if self.dialect not in ["mysql", "postgres"]:
            return

        # class settings
        asynctools.multitasking.createPool(__name__)
        self.symbol_ids = {}

        # initialize engine
        self.engine = create_engine(conn_str, echo=debug)

        # create database?
        dbs = self.engine.execute("SHOW DATABASES;")
        if dbname not in [d[0] for d in dbs]:
            self.engine.execute("CREATE DATABASE {0};".format(dbname))

        # select database
        self.engine.execute("USE {0}".format(dbname))

        # default insert function (for on_duplicate_key_update)
        self.insert = mysql.insert
        datetime_col = mysql.DATETIME(fsp=6)
        if self.dialect == "postgres":
            self.insert = insert
            datetime_col = DateTime()

        # define tables
        metadata = MetaData(bind=self.engine)

        self.symbols = Table(
            'symbols', metadata,
            Column('id', Integer, primary_key=True),
            Column('symbol', String(24), index=True),
            Column('symbol_group', String(18), index=True),
            Column('asset_class', String(3), index=True),
            Column('expiry', Date, index=True)
        )

        self.bars = Table(
            'bars', metadata,
            Column('id', Integer, primary_key=True),
            Column('datetime', DateTime, index=True),
            Column('symbol_id', Integer, ForeignKey("symbols.id"),
                   nullable=False, index=True),
            Column('open', Float),
            Column('high', Float),
            Column('low', Float),
            Column('close', Float),
            Column('volume', Integer),
            UniqueConstraint('datetime', 'symbol_id', name='uix_dt_sym')
        )

        self.ticks = Table(
            'ticks', metadata,
            Column('id', Integer, primary_key=True),
            Column('datetime', datetime_col, index=True),
            Column('symbol_id', Integer, ForeignKey("symbols.id"),
                   nullable=False, index=True),
            Column('bid', Float, nullable=True),
            Column('bidsize', Integer, nullable=True),
            Column('ask', Float, nullable=True),
            Column('asksize', Integer, nullable=True),
            Column('last', Float, nullable=True),
            Column('lastsize', Integer, nullable=True),
            UniqueConstraint('datetime', 'symbol_id', name='uix_dt_sym')
        )

        self.greeks = Table(
            'greeks', metadata,
            Column('id', Integer, primary_key=True),
            Column('tick_id', Integer, ForeignKey("ticks.id"),
                   nullable=True, index=True),
            Column('bar_id', Integer, ForeignKey("bars.id"),
                   nullable=True, index=True),
            Column('price', Float),
            Column('underlying', Float),
            Column('dividend', Float),
            Column('volume', Integer),
            Column('iv', Float),
            Column('oi', Float),
            Column('delta', Float(3, 2)),
            Column('gamma', Float(3, 2)),
            Column('theta', Float(3, 2)),
            Column('vega', Float(3, 2)),
        )

        self.conn = self.engine.connect()
        metadata.create_all(self.conn, checkfirst=True)

    # -----------------------------------
    def _update_on_conflict(self, query, update_params, constraint):
        if self.dialect == 'postgres':
            return query.on_conflict_do_update(
                constraint=constraint,
                set_=update_params)
        # else (mysql)
        return query.on_duplicate_key_update(**update_params)

    # -----------------------------------
    def get_symbol_id(self, symbol, expiry=None):

        # start
        params = {
            "symbol": symbol.split("_")[0],
            "asset_class": tools.gen_asset_class(symbol),
            "symbol_group": tools.gen_symbol_group(symbol),
        }
        params["symbol"] = symbol.replace("_" + params["asset_class"], "")

        where = and_(
            text("symbol=:symbol"),
            text("symbol_group=:symbol_group"),
            text("asset_class=:asset_class"),
            text("expiry=:expiry"),
        )

        if params["asset_class"] in ("FUT", "OPT", "FOP"):
            # look for symbol w/ expiry
            params["expiry"] = tools.contract_expiry_from_symbol(symbol)
            where = and_(where, text("expiry=:expiry"))

        # look for symbol w/o expiry
        q = self.symbols.select().where(where)
        row = self.conn.execute(q, **params).fetchone()

        # symbol already in db
        if row is not None:
            return row[0]

        # symbol/expiry not in db... insert new/update expiry
        transaction = self.conn.begin()
        q = self.symbols.insert().values(**params)
        res = self.conn.execute(q)
        try:
            transaction.commit()
            return res.lastrowid
        except Exception:
            transaction.rollback()
            return None

    # -----------------------------------

    @asynctools.multitasking.task
    def store(self, data, kind, greeks={}):
        if len(data["symbol"].split("_")) > 2:
            return

        if kind not in ["TICK", "BAR"]:
            return

        symbol_id = 0
        symbol = data["symbol"].replace("_" + data["asset_class"], "")

        if symbol in self.symbol_ids.keys():
            symbol_id = self.symbol_ids[symbol]
        else:
            symbol_id = self.get_symbol_id(data["symbol"])
            if not symbol_id:
                raise ValueError("get_symbol_id() Error")
            self.symbol_ids[symbol] = symbol_id

        # insert to db
        if kind == "TICK":
            q = self.insert(self.ticks).prefix_with("IGNORE").values(**{
                "symbol_id": symbol_id,
                "datetime": data["timestamp"],
                "bid": float(data["bid"]),
                "bidsize": int(data["bidsize"]),
                "ask": float(data["ask"]),
                "asksize": int(data["asksize"]),
                "last": float(data["last"]),
                "lastsize": int(data["lastsize"])
            })
            q = self._update_on_conflict(q, {
                "symbol_id": symbol_id
            }, 'uix_dt_sym')

        elif kind == "BAR":
            q = self.insert(self.bars).prefix_with("IGNORE").values(**{
                "symbol_id": symbol_id,
                "datetime": data["timestamp"],
                "open": float(data["open"]),
                "high": float(data["high"]),
                "low": float(data["low"]),
                "close": float(data["close"]),
                "volume": int(data["volume"])
            })

            q = self._update_on_conflict(q, {
                "open": float(data["open"]),
                "high": float(data["high"]),
                "low": float(data["low"]),
                "close": float(data["close"]),
                "volume": int(data["volume"])
            }, 'uix_dt_sym')

        transaction = self.conn.begin()
        try:
            res = self.conn.execute(q)
            transaction.commit()
            lastrow_id = res.lastrowid
        except Exception:
            transaction.rollback()
            raise

        # add greeks?
        hasgreeks = any([greeks[key] for key in greeks.keys() if "opt" in key])
        if hasgreeks:
            greeks = {
                "price": round(float(greeks["opt_price"]), 2),
                "underlying": round(float(greeks["opt_underlying"]), 5),
                "dividend": float(greeks["opt_dividend"]),
                "volume": int(greeks["opt_volume"]),
                "iv": float(greeks["opt_iv"]),
                "oi": float(greeks["opt_oi"]),
                "delta": float(greeks["opt_delta"]),
                "gamma": float(greeks["opt_gamma"]),
                "theta": float(greeks["opt_theta"]),
                "vega": float(greeks["opt_vega"])
            }
            if kind == "TICK":
                greeks["tick_id"] = lastrow_id
            elif kind == "BAR":
                greeks["bar_id"] = lastrow_id

            q = self.insert(self.greeks).prefix_with("IGNORE").values(**greeks)
            transaction = self.conn.begin()
            try:
                res = self.conn.execute(q)
                transaction.commit()
                return res.lastrowid
            except Exception:
                transaction.rollback()
                pass

    # -----------------------------------
    def history(self, symbols, start, end=None,
                resolution="1T", tz="UTC", continuous=True):

        resolution = resolution.upper()

        # load runtime/default data
        if isinstance(symbols, str):
            symbols = symbols.split(',')

        # work with symbol groups
        symbol_groups = list(map(tools.gen_symbol_group, symbols))
        # print(symbol_groups)

        # convert datetime to string for MySQL
        try:
            start = start.strftime(
                ibDataTypes["DATE_TIME_FORMAT_LONG_MILLISECS"])
        except Exception:
            pass

        if end is not None:
            try:
                end = end.strftime(
                    ibDataTypes["DATE_TIME_FORMAT_LONG_MILLISECS"])
            except Exception:
                pass

        # --- build query
        table = 'ticks' if resolution[-1] in ("K", "V", "S") else 'bars'

        q = """SELECT tbl.*,
                CONCAT(s.`symbol`, "_", s.`asset_class`) as symbol,
                s.symbol_group, s.asset_class, s.expiry, g.price AS opt_price,
                g.underlying AS opt_underlying, g.dividend AS opt_dividend,
                g.volume AS opt_volume, g.iv AS opt_iv, g.oi AS opt_oi,
                g.delta AS opt_delta, g.gamma AS opt_gamma,
                g.theta AS opt_theta, g.vega AS opt_vega
                FROM `{TABLE}` tbl
                LEFT JOIN `symbols` s ON tbl.symbol_id = s.id
                LEFT JOIN `greeks` g ON tbl.id = g.{TABLE_ID}
                WHERE (`datetime` >= "{START}"{END_SQL}) """

        if end is not None:
            q = q.replace('{END_SQL}', ' AND `datetime` <= "{END}"')
            q = q.replace('{END}', end)
        else:
            q = q.replace('{END_SQL}', '')

        if symbols[0].strip() != "*":
            if continuous:
                q += """ AND ( s.`symbol_group` in ("{SYMBOL_GROUPS}") OR
                         CONCAT(s.`symbol`, "_", s.`asset_class`)
                         IN ("{SYMBOLS}") ) """
            else:
                q += """ AND ( CONCAT(s.`symbol`, "_", s.`asset_class`)
                         IN ("{SYMBOLS}") ) """

        q = q.replace('{START}', start)
        q = q.replace('{TABLE}', table)
        q = q.replace('{TABLE_ID}', table[:-1] + '_id')
        q = q.replace('{SYMBOLS}', '","'.join(symbols))
        q = q.replace('{SYMBOL_GROUPS}', '","'.join(symbol_groups))

        # --- end build query

        # get data using pandas
        data = pd.read_sql(q, self.conn)

        # no data in db
        if data.empty:
            return data

        # clearup records that are out of sequence
        return self._fix_history_sequence(data, table)

    # -----------------------------------

    def _fix_history_sequence(self, df, table):
        """ fix out-of-sequence ticks/bars """

        # remove "Unnamed: x" columns
        cols = df.columns[df.columns.str.startswith('Unnamed:')].tolist()
        df.drop(cols, axis=1, inplace=True)

        # remove future dates
        df['datetime'] = pd.to_datetime(df['datetime'], utc=True)
        blacklist = df[df['datetime'] > pd.to_datetime('now', utc=True)]
        df = df.loc[set(df.index) - set(blacklist)]  # .tail()

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
            malformed = data.shift(1)[(data['id'] > data['id'].shift(1)) & (
                data['datetime'] < data['datetime'].shift(1))]

            # cleanup rows
            if malformed.empty:
                # if all rows are in sequence, just remove last row
                dfs.append(data)
            else:
                # remove out of sequence rows + last row from data
                index = [x for x in data.index.values
                         if x not in malformed['ix'].values]
                dfs.append(data.loc[index])

                # add to bad id list (to remove from db)
                bad_ids.append(list(malformed['id'].values))

        # combine all lists
        data = pd.concat(dfs, sort=True)

        # flatten bad ids
        bad_ids = sum(bad_ids, [])

        # remove bad ids from db
        if bad_ids:
            bad_ids = list(map(str, map(int, bad_ids)))

            transaction = self.conn.begin()
            try:
                self.conn.execute("DELETE FROM greeks WHERE %s IN (%s)" % (
                    table.lower()[:-1] + "_id", ",".join(bad_ids)))
                self.conn.execute("DELETE FROM " + table.lower() +
                                  " WHERE id IN (%s)" % (",".join(bad_ids)))
                transaction.commit()
            except Exception:
                transaction.rollback()

        # return
        return data.drop(['id', 'ix', 'index'], axis=1)

    # -----------------------------------

    def close(self):
        self.conn.close()
