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

import numpy as np
import pandas as pd
import warnings

from datetime import datetime, timedelta
from pandas.core.base import PandasObject

warnings.simplefilter(action = "ignore", category = RuntimeWarning)

# =============================================
# remove previous globex day from df
# =============================================
def session(df, start='17:00', end='16:00'):

    if len(df) == 0:
        return df

    # get start/end/now as decimals
    int_start = list(map(int, start.split(':')))
    int_start = (int_start[0]+int_start[1]-1/100)-0.0001
    int_end   = list(map(int, end.split(':')))
    int_end   = int_end[0]+int_end[1]/100
    int_now   = (df[-1:].index.hour[0]+(df[:1].index.minute[0])/100)

    # same-dat session?
    is_same_day = int_end > int_start

    # set pointers
    curr = prev = df[-1:].index[0].strftime('%Y-%m-%d')

    # globex/forex session
    if is_same_day == False:
        prev = (datetime.strptime(curr, '%Y-%m-%d')-timedelta(1)).strftime('%Y-%m-%d')

    # slice
    if int_now >= int_start:
        df = df[ df.index >= curr+' '+start ]
    else:
        df = df[ df.index >= prev+' '+start ]


    return df

# ---------------------------------------------------------
def heikinashi(df, columns=('open', 'high', 'low', 'close')):
    ha_close = (df[columns[0]] + df[columns[1]] + df[columns[2]] + df[columns[3]]) / 4
    ha_open  = (df[columns[0]].shift(1) + df[columns[3]].shift(1)) / 2
    ha_high  = df.loc[:, ['high', 'ha_open', 'ha_close']].max(axis=1)
    ha_low   = df.loc[:, ['low', 'ha_open', 'ha_close']].min(axis=1)

    return pd.DataFrame(index=df.index, data={'open': ha_open, 'high':ha_high, 'low':ha_low, 'close':ha_close})

# ---------------------------------------------------------
def nans(len=1):
    mtx = np.empty(len)
    mtx[:] = np.nan
    return mtx

# ---------------------------------------------------------
def typical_price(bars):
    res = (bars['high'] + bars['low'] + bars['close']) / 3.
    return pd.Series(index=bars.index, data=res)

# ---------------------------------------------------------
def mid_price(bars):
    res = (bars['high'] + bars['low']) / 2.
    return pd.Series(index=bars.index, data=res)

# ---------------------------------------------------------
def ibs(bars):
    """ Internal bar strength """
    res = np.round((bars['close']-bars['low']) / (bars['high']-bars['low']), 2)
    return pd.Series(index=bars.index, data=res)

# ---------------------------------------------------------
def true_range(bars):
    return pd.DataFrame({
        "hl": bars['high']-bars['low'],
        "hc": abs(bars['high'] - bars['close'].shift(1)),
        "lc": abs(bars['low'] - bars['close'].shift(1))
      }).max(axis=1)

# ---------------------------------------------------------
def atr(bars, window=14, exp=False):
    tr = true_range(bars)

    if exp:
        res = rolling_weighted_mean(tr, window)
    else:
        res = rolling_mean(tr, window)

    res = pd.Series(res)
    return (res.shift(1)*(window-1)+res)/window

# ---------------------------------------------------------
def crossed_above(series1, series2):
    return pd.Series((series1 > series2) & (series1.shift(1) <= series2.shift(1)))

# ---------------------------------------------------------
def crossed_below(series1, series2):
    return pd.Series((series1 < series2) & (series1.shift(1) >= series2.shift(1)))

# ---------------------------------------------------------
def rolling_std(series, window=200, min_periods=None):
    if min_periods is None: min_periods = window
    try:
        try:
            return series.rolling(window=window, min_periods=min_periods).std()
        except:
            return pd.Series(series).rolling(window=window, min_periods=min_periods).std()
    except:
        return pd.rolling_std(series, window=window, min_periods=min_periods)

# ---------------------------------------------------------
def rolling_mean(series, window=200, min_periods=None):
    if min_periods is None: min_periods = window
    try:
        try:
            return series.rolling(window=window, min_periods=min_periods).mean()
        except:
            return pd.Series(series).rolling(window=window, min_periods=min_periods).mean()
    except:
        return pd.rolling_mean(series, window=window, min_periods=min_periods)

# ---------------------------------------------------------
def rolling_min(series, window=14, min_periods=None):
    if min_periods is None: min_periods = window
    try:
        try:
            return series.rolling(window=window, min_periods=min_periods).min()
        except:
            return pd.Series(series).rolling(window=window, min_periods=min_periods).min()
    except:
        return pd.rolling_min(series, window=window, min_periods=min_periods)

# ---------------------------------------------------------
def rolling_max(series, window=14, min_periods=None):
    if min_periods is None: min_periods = window
    try:
        try:
            return series.rolling(window=window, min_periods=min_periods).min()
        except:
            return pd.Series(series).rolling(window=window, min_periods=min_periods).min()
    except:
        return pd.rolling_min(series, window=window, min_periods=min_periods)

# ---------------------------------------------------------
def rolling_weighted_mean(series, window=200, min_periods=None):
    if min_periods is None: min_periods = window
    try:
        return series.ewm(span=window, min_periods=min_periods).mean()
    except:
        return pd.ewma(series, span=window, min_periods=min_periods)

# ---------------------------------------------------------
def hull_moving_average(series, window=200):
    wma = (2*rolling_weighted_mean(series, window=window/2)) - rolling_weighted_mean(series, window=window)
    return rolling_weighted_mean(wma, window=np.sqrt(window))

# ---------------------------------------------------------
def sma(series, window=200, min_periods=None):
    return rolling_mean(series, window=window, min_periods=min_periods)

def wma(series, window=200, min_periods=None):
    return rolling_weighted_mean(series, window=window, min_periods=min_periods)

def hma(series, window=200):
    return hull_moving_average(series, window=window)

# ---------------------------------------------------------
def vwap(bars):
    """
    calculate vwap of entire time series
    (input can be pandas series or numpy array)
    bars are usually mid [ (h+l)/2 ] or typical [ (h+l+c)/3 ]
    """
    typical = ((bars['high']+bars['low']+bars['close'])/3).values
    volume  = bars['volume'].values
    res     = np.cumsum(volume*typical) / np.cumsum(volume)

    return pd.Series(index=bars.index, data=res)

# ---------------------------------------------------------
def rolling_vwap(bars, window=200, min_periods=None):
    """
    calculate vwap using moving window
    (input can be pandas series or numpy array)
    bars are usually mid [ (h+l)/2 ] or typical [ (h+l+c)/3 ]
    """
    if min_periods is None: min_periods = window

    typical = ((bars['high']+bars['low']+bars['close'])/3)
    volume  = bars['volume']

    left  = (volume*typical).rolling(window=window, min_periods=min_periods).sum()
    right = volume.rolling(window=window, min_periods=min_periods).sum()
    res     = left/right

    return pd.Series(index=bars.index, data=res)

# ---------------------------------------------------------
def rsi(series, window=14):
    """
    compute the n period relative strength indicator
    """
    # 100-(100/relative_strength)
    deltas = np.diff(series)
    seed = deltas[:window+1]

    # default values
    ups = seed[seed > 0].sum()/window
    downs = -seed[seed < 0].sum()/window
    rsival = np.zeros_like(series)
    rsival[:window] = 100.-100./(1.+ups/downs)

    # period values
    for i in range(window, len(series)):
        delta = deltas[i-1]
        if delta > 0:
            upval = delta
            downval = 0
        else:
            upval = 0
            downval = -delta

        ups = (ups*(window-1)+upval)/window
        downs = (downs*(window-1.)+downval)/window
        rsival[i] = 100.-100./(1.+ups/downs)

    # return rsival
    return pd.Series(index=series.index, data=rsival)

# ---------------------------------------------------------
def macd(series, fast=3, slow=10, smooth=16):
    """
    compute the MACD (Moving Average Convergence/Divergence)
    using a fast and slow exponential moving avg'
    return value is emaslow, emafast, macd which are len(x) arrays
    """
    macd   = rolling_weighted_mean(series, window=fast) - rolling_weighted_mean(series, window=slow)
    signal = rolling_weighted_mean(macd, window=smooth)
    histogram = macd-signal
    # return macd, signal, histogram
    return pd.DataFrame(index=series.index, data={
        'macd': macd.values,
        'signal': signal.values,
        'histogram': histogram.values
    })

# ---------------------------------------------------------
def bollinger_bands(series, window=20, stds=2):
    sma = rolling_mean(series, window=window)
    std = rolling_std(series, window=window)
    upper = sma + std * stds
    lower = sma - std * stds

    return pd.DataFrame(index=series.index, data={
        'upper': upper.values,
        'mid':   sma.values,
        'lower': lower.values
    })

# ---------------------------------------------------------
def weighted_bollinger_bands(series, window=20, stds=2):
    ema = rolling_weighted_mean(series, window=window)
    std = rolling_std(series, window=window)
    upper = ema + std * stds
    lower = ema - std * stds

    return pd.DataFrame(index=series.index, data={
        'upper': upper.values,
        'mid':   ema.values,
        'lower': lower.values
    })

# ---------------------------------------------------------
def returns(series):
    try:
        res = (series / series.shift(1) - 1).replace([np.inf, -np.inf], float('NaN'))
    except:
        res = nans(len(series))

    return pd.Series(index=series.index, data=res)

# ---------------------------------------------------------
def log_returns(series):
    try:
        res = np.log(series / series.shift(1)).replace([np.inf, -np.inf], float('NaN'))
    except:
        res = nans(len(series))

    return pd.Series(index=series.index, data=res)

# ---------------------------------------------------------
def implied_volatility(series, window=252):
    try:
        logret = np.log(series / series.shift(1)).replace([np.inf, -np.inf], float('NaN'))
        try:
            res = logret.rolling(window=window).std() * np.sqrt(window)
        except:
            res = pd.rolling_std(logret, window=window) * np.sqrt(window)
        return res
    except:
        res = nans(len(series))

    return pd.Series(index=series.index, data=res)

# ---------------------------------------------------------
def keltner_channel(bars, window=14, atrs=2):
    typical_mean = rolling_mean(typical_price(bars), window)
    atrval = atr(bars, window) * atrs

    upper = typical_mean + atrval
    lower = typical_mean - atrval

    return pd.DataFrame(index=bars.index, data={
        'upper': upper.values,
        'mid': typical_mean.values,
        'lower': lower.values
    })

# ---------------------------------------------------------
def roc(series, window=14):
    """
    compute rate of change
    """
    res = (series - series.shift(window)) / series.shift(window)
    return pd.Series(index=series.index, data=res)

# ---------------------------------------------------------
def cci(series, window=14):
    """
    compute commodity channel index
    """
    price = typical_price(series)
    typical_mean  = rolling_mean(price, window)
    res = (price - typical_mean) / (.015 * np.std(typical_mean))
    return pd.Series(index=series.index, data=res)

# ---------------------------------------------------------
def stoch(bars, window=14, slow=False, slow_ma=3):
    """
    compute the n period relative strength indicator
    http://excelta.blogspot.co.il/2013/09/stochastic-oscillator-technical.html
    """
    highs_ma = pd.concat([bars['highs'].shift(i) for i in np.arange(window)], 1).apply(list, 1)
    highs_ma = highs_ma.T.max().T

    lows_ma = pd.concat([bars['lows'].shift(i) for i in np.arange(window)], 1).apply(list, 1)
    lows_ma = lows_ma.T.min().T

    k = ((bars['close']-lows_ma) / (highs_ma-lows_ma)) * 100

    # for fast we just take the stochastic value, slow we need 3 day MA
    if slow:
        k = rolling_mean(k, window=slow_ma)

    r = rolling_mean(k, window=window)

    return pd.DataFrame(index=bars.index, data={ 'k': k, 'r': r })

# ---------------------------------------------------------
PandasObject.session                  = session
PandasObject.atr                      = atr
PandasObject.bollinger_bands          = bollinger_bands
PandasObject.cci                      = cci
PandasObject.crossed_above            = crossed_above
PandasObject.crossed_below            = crossed_below
PandasObject.heikinashi               = heikinashi
PandasObject.hull_moving_average      = hull_moving_average
PandasObject.ibs                      = ibs
PandasObject.implied_volatility       = implied_volatility
PandasObject.keltner_channel          = keltner_channel
PandasObject.log_returns              = log_returns
PandasObject.macd                     = macd
PandasObject.returns                  = returns
PandasObject.roc                      = roc
PandasObject.rolling_max              = rolling_max
PandasObject.rolling_min              = rolling_min
PandasObject.rolling_mean             = rolling_mean
PandasObject.rolling_std              = rolling_std
PandasObject.rsi                      = rsi
PandasObject.stoch                    = stoch
PandasObject.true_range               = true_range
PandasObject.mid_price                = mid_price
PandasObject.typical_price            = typical_price
PandasObject.vwap                     = vwap
PandasObject.rolling_vwap             = rolling_vwap
PandasObject.weighted_bollinger_bands = weighted_bollinger_bands
PandasObject.rolling_weighted_mean    = rolling_weighted_mean

PandasObject.sma = sma
PandasObject.wma = wma
PandasObject.hma = hma
