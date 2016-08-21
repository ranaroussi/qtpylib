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

import datetime
import numpy as np
import pandas as pd
import time

from dateutil.relativedelta import relativedelta, FR
from dateutil.parser import parse as parse_date
from pytz import timezone


# =============================================
def as_dict(df, ix=":"):

    ix = str(ix).strip()
    org_ix = str(ix)

    try: ix = int(ix)
    except: pass

    start = ix
    end = ''

    if isinstance(ix, int):
        if ix > 0:
            start = ix
            end = ix+1
        elif ix < 0:
            start = ix
            if ix < -1: end = ix+1
        else:
            start = ''
            end = 1

        ix = str(start)+':'+str(end)

    slicer = slice(*[{True: lambda n: None, False: int}[x == ''](x) \
        for x in (ix.split(':') + ['', '', ''])[:3]])

    if isinstance(df.index, pd.DatetimeIndex):
        df.loc[slicer, 'datetime'] = df[slicer].index

    df_dict = df[slicer].to_dict(orient='records')

    if ":" not in org_ix or len(df_dict) == 1:
        return df_dict[0]

    return df_dict

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

    date = parse_date(date_str+tz_offset)
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

    def resample_ticks(df, freq=1000, price_col='last', volume_col=None):
        """
        function that re-samples tick data into an N-tick-chart ready OHLC(V) format

        df = pandas pd.dataframe tick data
        price_col = the Price column name
        volume_col = the Volume column name (if applicable)
        freq = tick resoltuin grouping
        """

        # get only ticks and fill missing data
        cols = [price_col]
        if volume_col:
            cols.append(volume_col)
        ticks = df.ix[:, cols]

        # place timestamp index in T colums
        # (to be used as future df index)
        ticks['T'] = ticks.index

        # add group indicator evey N ticks
        ticks['grp'] = [np.nan if i%freq else i for i in range(len(ticks[price_col]))]
        ticks.fillna(method='ffill', inplace=True)
        ticks = ticks.set_index('grp')

        # grop ticks
        groupped = ticks.groupby(ticks.index, sort=False)

        # build ohlc(v) pd.dataframe from new grp column
        tickdf = pd.DataFrame({'open': groupped[price_col].first()})
        tickdf['high']  = groupped[price_col].max()
        tickdf['low']   = groupped[price_col].min()
        tickdf['close'] = groupped[price_col].last()
        if volume_col:
            tickdf['volume'] = groupped[volume_col].sum()

        # set index to timestamp
        tickdf['datetime'] = groupped.T.head(1)
        tickdf.set_index(['datetime'], inplace=True)

        return tickdf


    if len(data) > 0:

        # resample
        periods = int("".join([s for s in resolution if s.isdigit()]))
        meta_data = data.groupby(["symbol"])[['symbol', 'symbol_group', 'asset_class']].last()
        combined = []

        if ("K" in resolution):
            if (periods > 1):
                for sym in meta_data.index.values:
                    symdata = resample_ticks(data[data['symbol']==sym], periods, price_col='last', volume_col='lastsize')
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
def round_to_fraction(val, res, decimals=2):
    """ round to closest resolution """
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
        elif "H" in res:
            new_date = date - datetime.timedelta(hours=periods)
        elif "W" in res:
            new_date = date - datetime.timedelta(weeks=periods)
        else: # days
            new_date = date - datetime.timedelta(days=periods)

        # not a week day:
        while new_date.weekday() > 4: # Mon-Fri are 0-4
            new_date = backdate(res=res, date=new_date, as_datetime=True)

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

        if ".csv" in self.output_file:
            self.recorded.to_csv(self.output_file)
        elif ".h5" in self.output_file:
            self.recorded.to_hdf(self.output_file, 0)
        elif (".pickle" in self.output_file) | (".pkl" in self.output_file):
            self.recorded.to_pickle(self.output_file)

