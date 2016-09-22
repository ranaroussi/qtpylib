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

import datetime
import numpy as np
import pandas as pd
import time
import os
from stat import S_IWRITE

from dateutil.relativedelta import relativedelta, FR
from dateutil.parser import parse as parse_date
from pytz import timezone

# =============================================
def chmod(f):
    """ change mod to writeable """
    try: os.chmod(f, S_IWRITE) # windows (cover all)
    except: pass
    try: os.chmod(f, 0o777) # *nix
    except: pass

# =============================================
def as_dict(df, ix=':'):
    """ converts df to dict and adds a datetime field if df is datetime """
    if isinstance(df.index, pd.DatetimeIndex):
        df['datetime'] = df.index
    return df.to_dict(orient='records')[ix]

# =============================================
# utility to get the machine's timeozone
# =============================================
def get_timezone():
    if time.daylight:
        offsetHour = time.altzone / 3600
    else:
        offsetHour = time.timezone / 3600
    return 'Etc/GMT%+d' % offsetHour


def datetime_to_timezone(date, tz="UTC"):
    if not date.tzinfo:
        date = date.replace(tzinfo=timezone(get_timezone()))
    return date.astimezone(timezone(tz))


def convert_timezone(date_str, tz_from, tz_to="UTC", fmt=None):
    # get timezone as tz_offset
    tz_offset = datetime_to_timezone(datetime.datetime.now(), tz=tz_from).strftime('%z')
    tz_offset = tz_offset[:3]+':'+tz_offset[3:]

    date = parse_date(str(date_str)+tz_offset)
    if tz_from != tz_to:
        date = datetime_to_timezone(date, tz_to)

    if isinstance(fmt, str):
        return date.strftime(fmt)
    return date

# =============================================
# utility to change the timeozone to specified one
# =============================================
def set_timezone(data, tz=None, from_local=False):
    # pandas object?
    if isinstance(data, pd.DataFrame) | isinstance(data, pd.Series):
        try:
            try:
                data.index = data.index.tz_convert(tz)
            except:
                if from_local:
                    data.index = data.index.tz_localize(get_timezone()).tz_convert(tz)
                else:
                    data.index = data.index.tz_localize('UTC').tz_convert(tz)
        except: pass

    # not pandas...
    else:
        if isinstance(data, str):
            data = parse_date(data)
        try:
            try:
                data = data.astimezone(tz)
            except:
                data = timezone('UTC').localize(data).astimezone(timezone(tz))
        except: pass

    return data

# =============================================
# set timezone for pandas
# =============================================
def fix_timezone(df, freq, tz=None):
    index_name = df.index.name

    # fix timezone
    if isinstance(df.index[0], str):
        # timezone df exists
        if ("-" in df.index[0][-6:]) | ("+" in df.index[0][-6:]):
            df.index = pd.to_datetime(df.index, utc=False)
            df.index = df.index.tz_localize('UTC').tz_convert(tz)

        # no timezone df - do some resampling
        else:
            # original range
            start_range = df.index[0]
            end_range   = df.index[-1]

            # resample df
            df.index = pd.to_datetime(df.index, utc=True)
            df = resample(df, freq=freq, ffill=False, dropna=False)

            # create date range
            new_freq = ''.join(i for i in freq if not i.isdigit())
            rng = pd.date_range(start=start_range, end=end_range, tz=tz, freq=new_freq)

            # assign date range to df and drop empty rows
            df.index = rng
            df.dropna(inplace=True)

    # finalize timezone (also for timezone-aware df)
    df = set_timezone(df, tz=tz)

    df.index.name = index_name
    return df

# ===========================================
# resample baed on time / tick count
# ===========================================
def resample(data, resolution="1T", tz=None, ffill=True, dropna=False):

    def resample_ticks(data, freq=1000, by='last'):
        """
        function that re-samples tick data into an N-tick or N-volume OHLC format

        df = pandas pd.dataframe of raw tick data
        freq = resoltuin grouping
        by = the column name to resample by
        """

        # place timestamp index in T colums
        # (to be used as future df index)
        data['T'] = data.index

        # get only ticks and fill missing data
        try:
            df = data[['T', 'last', 'lastsize']].copy()
            price_col = 'last'
            size_col  = 'lastsize'
        except:
            df = data[['T', 'close', 'volume']].copy()
            price_col = 'close'
            size_col  = 'volume'

        # add group indicator evey N df
        if by == 'size' or by == 'lastsize' or by == 'volume':
            df['cumvol'] = df[size_col].cumsum()
            df['mark'] = round(round(round(df['cumvol'] / .1)*.1, 2)/freq) * freq
            df['diff'] = df['mark'].diff().fillna(0).astype(int)
            df['grp'] = np.where(df['diff']>=freq-1, (df['mark']/freq), np.nan)
        else:
            df['grp'] = [np.nan if i%freq else i for i in range(len(df[price_col]))]

        df.loc[:1, 'grp'] = 0

        df.fillna(method='ffill', inplace=True)
        # print(df[['lastsize', 'cumvol', 'mark', 'diff', 'grp']].tail(1))
        df = df.set_index('grp')

        # grop df
        groupped = df.groupby(df.index, sort=False)

        # build ohlc(v) pd.dataframe from new grp column
        newdf = pd.DataFrame({
            'open':   groupped[price_col].first(),
            'high':   groupped[price_col].max(),
            'low':    groupped[price_col].min(),
            'close':  groupped[price_col].last(),
            'volume': groupped[size_col].sum()
        })

        # set index to timestamp
        newdf['datetime'] = groupped.T.head(1)
        newdf.set_index(['datetime'], inplace=True)

        return newdf


    if len(data) > 0:

        # resample
        periods = int("".join([s for s in resolution if s.isdigit()]))
        meta_data = data.groupby(["symbol"])[['symbol', 'symbol_group', 'asset_class']].last()
        combined = []

        if ("K" in resolution):
            if (periods > 1):
                for sym in meta_data.index.values:
                    # symdata = resample_ticks(data[data['symbol']==sym], periods, price_col='last', volume_col='lastsize')
                    symdata = resample_ticks(data[data['symbol']==sym], freq=periods, by='last')
                    symdata['symbol'] = sym
                    symdata['symbol_group'] = meta_data[meta_data.index==sym]['symbol_group'].values[0]
                    symdata['asset_class'] = meta_data[meta_data.index==sym]['asset_class'].values[0]
                    combined.append(symdata)

                data = pd.concat(combined).dropna()

        elif ("V" in resolution):
            if (periods > 1):
                for sym in meta_data.index.values:
                    symdata = resample_ticks(data[data['symbol']==sym], freq=periods, by='lastsize')
                    # print(symdata)
                    symdata['symbol'] = sym
                    symdata['symbol_group'] = meta_data[meta_data.index==sym]['symbol_group'].values[0]
                    symdata['asset_class'] = meta_data[meta_data.index==sym]['asset_class'].values[0]
                    combined.append(symdata)

                data = pd.concat(combined).dropna()

        # continue...
        else:
            ohlc_dict = {
                'open':   'first',
                'high':   'max',
                'low':    'min',
                'close':  'last',
                'volume': 'sum'
            }

            for sym in meta_data.index.values:
                if ("S" in resolution):
                    ohlc = data[data['symbol']==sym]['last'].resample(resolution).ohlc()
                    vol  = data[data['symbol']==sym]['lastsize'].resample(resolution).sum()
                    symdata = ohlc
                    symdata['volume'] = vol
                else:
                    original_length = len(data[data['symbol']==sym])
                    symdata = data[data['symbol']==sym].resample(resolution).apply(ohlc_dict).dropna()

                    # deal with new rows caused by resample
                    if len(symdata) > original_length:
                        # volume is 0 on rows created using resample
                        symdata['volume'].fillna(0, inplace=True)
                        symdata['volume'] = symdata['volume'].astype(int)
                        symdata.ffill(inplace=True)

                        # no fill / return original index
                        if ffill:
                            symdata['open']  = np.where(symdata['volume']<=0, symdata['close'], symdata['open'])
                            symdata['high']  = np.where(symdata['volume']<=0, symdata['close'], symdata['high'])
                            symdata['low']   = np.where(symdata['volume']<=0, symdata['close'], symdata['low'])
                        else:
                            symdata['open']  = np.where(symdata['volume']<=0, np.nan, symdata['open'])
                            symdata['high']  = np.where(symdata['volume']<=0, np.nan, symdata['high'])
                            symdata['low']   = np.where(symdata['volume']<=0, np.nan, symdata['low'])
                            symdata['close'] = np.where(symdata['volume']<=0, np.nan, symdata['close'])

                    # drop NANs
                    if dropna:
                        symdata.dropna(inplace=True)

                symdata['symbol'] = sym
                symdata['symbol_group'] = meta_data[meta_data.index==sym]['symbol_group'].values[0]
                symdata['asset_class'] = meta_data[meta_data.index==sym]['asset_class'].values[0]
                combined.append(symdata)

            data = pd.concat(combined).dropna()

    # figure out timezone
    if tz is None:
        try:
            tz = str(data.index.tz)
        except:
            tz = None

    if tz is not None:
        try:
            data.index = data.index.tz_convert(tz)
        except:
            data.index = data.index.tz_localize('UTC').tz_convert(tz)

    return data

# -------------------------------------------
class make_object:
    def __init__(self, **entries):
        self.__dict__.update(entries)

# -------------------------------------------
def round_to_fraction(val, res, decimals=None):
    """ round to closest resolution """
    if decimals is None and "." in str(res):
        decimals = len(str(res).split('.')[1])

    return round(round(val / res)*res, decimals)

# -------------------------------------------
def backdate(res, date=None, as_datetime=False, fmt='%Y-%m-%d', tz="UTC"):
    if date is None:
        date = datetime.datetime.now()
    else:
        try: date = parse_date(date)
        except: pass

    new_date = date

    periods = int("".join([s for s in res if s.isdigit()]))

    if periods > 0:

        if "K" in res:
            new_date = date - datetime.timedelta(microseconds=periods)
        elif "S" in res:
            new_date = date - datetime.timedelta(seconds=periods)
        elif "T" in res:
            new_date = date - datetime.timedelta(minutes=periods)
        elif "H" in res or "V" in res:
            new_date = date - datetime.timedelta(hours=periods)
        elif "W" in res:
            new_date = date - datetime.timedelta(weeks=periods)
        else: # days
            new_date = date - datetime.timedelta(days=periods)

        # not a week day:
        while new_date.weekday() > 4: # Mon-Fri are 0-4
            new_date = backdate(res="1D", date=new_date, as_datetime=True)

    if as_datetime:
        return new_date
    else:
        return new_date.strftime(fmt)

# -------------------------------------------
def previous_weekday(day=None, as_datetime=False):
    if day is None:
        day = datetime.datetime.now()
    else:
        day = datetime.datetime.strptime(day, '%Y-%m-%d')

    day -= datetime.timedelta(days=1)
    while day.weekday() > 4: # Mon-Fri are 0-4
        day -= datetime.timedelta(days=1)

    if as_datetime:
        return day
    return day.strftime("%Y-%m-%d")

# -------------------------------------------
def is_third_friday(day=None):
    if day is None: day = datetime.datetime.now()
    defacto_friday = (day.weekday() == 4) or (day.weekday() == 3 and day.hour() >= 17)
    return defacto_friday and 14 < day.day < 22

# -------------------------------------------
def after_third_friday(day=None):
    if day is None: day = datetime.datetime.now()
    now = day.replace(day=1, hour=16, minute=0, second=0, microsecond=0)
    now += relativedelta(weeks=2, weekday=FR)
    return day > now


# ===========================================
# store event in a temp data store
# ===========================================
class DataStore():
    def __init__(self, output_file=None):
        self.auto = None
        self.recorded = None
        self.output_file = output_file

    def record(self, timestamp, *args, **kwargs):
        """ add custom data to data store """
        if self.output_file is None:
            return

        data = {}

        # append all data
        if len(args) == 1:
            if isinstance(args[0], dict):
                data.update(dict(args[0]))
            elif isinstance(args[0], pd.DataFrame):
                data.update(args[0][-1:].to_dict(orient='records')[0])

        # add kwargs
        if len(kwargs) > 0:
            data.update(dict(kwargs))


        # set the datetime
        data['datetime'] = timestamp

        # take datetime from index
        if self.recorded is not None:
            self.recorded['datetime'] = self.recorded.index

        row = pd.DataFrame(data=data, index=[timestamp])
        if self.recorded is None:
            self.recorded = row
        else:
            self.recorded.merge(row)
            self.recorded = pd.concat([self.recorded, row])

        # merge rows
        self.recorded = self.recorded.groupby(self.recorded.index).sum()
        self.recorded.index.rename('datetime', inplace=True)

        # forward fill positions
        if "position" in self.recorded.columns:
            self.recorded['position'].ffill(inplace=True)

        if ".csv" in self.output_file:
            self.recorded.to_csv(self.output_file)
        elif ".h5" in self.output_file:
            self.recorded.to_hdf(self.output_file, 0)
        elif (".pickle" in self.output_file) | (".pkl" in self.output_file):
            self.recorded.to_pickle(self.output_file)

        chmod(self.output_file)