#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# QTPy: Light-Weight, Pythonic Algorithmic Trading Library
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
import os.path
import pandas as pd
import numpy as np
import requests
import re
import time
import tempfile

from bs4 import BeautifulSoup as bs
from dateutil.parser import parse as parse_date
from io import StringIO

from qtpylib import tools

import logging
logging.getLogger('requests').setLevel(logging.WARNING)

# -------------------------------------------
def create_continous_contract(df, resolution="1T"):

    def _merge_contracts(m1, m2):

        if m1 is None:
            return m2

        try:
            # rollver by date
            roll_date = m1['expiry'].unique()[-1]
        except:
            # rollover by volume
            combined  = m1.merge(m2, left_index=True, right_index=True)
            m_highest = combined['volume_y'] > combined['volume_x']
            if len(m_highest.index) == 0:
                return m1 # didn't rolled over yet
            roll_date = m_highest[m_highest].index[-1]


        return pd.concat([ m1[m1.index<=roll_date], m2[m2.index>roll_date] ])


    def _continous_contract_flags(daily_df):
        # grab expirations
        expirations = list(daily_df['expiry'].dropna().unique())
        expirations.sort()

        # set continous contract markets
        flags = None
        for expiration in expirations:
            new_contract = daily_df[daily_df['expiry']==expiration].copy()
            flags = _merge_contracts(flags, new_contract)

        # add gap
        flags['gap'] = 0
        for expiration in expirations:
            try:
                minidf = daily_df[daily_df.index==expiration][['symbol', 'expiry', 'diff']]
                expiry = flags[
                    (flags.index>expiration) & (flags['expiry']>=expiration)
                ]['expiry'][0]
                gap = minidf[minidf['expiry']==expiry]['diff'][0]
                flags.loc[flags.index<=expiration, 'gap'] = gap
            except:
                pass

        flags = flags[flags['symbol'].isin(flags['symbol'].unique())]

        # single row df won't resample
        if len(flags.index) <= 1:
            flags = pd.DataFrame(index=pd.date_range(start=flags[0:1].index[0],
                periods=24, freq="1H"), data=flags[['symbol', 'expiry', 'gap']]).ffill()

        flags['expiry'] = pd.to_datetime(flags['expiry'], utc=True)
        return flags[['symbol', 'expiry', 'gap']]

    # gonna need this later
    df['datetime'] = df.index

    # work with daily data
    daily_df = df.groupby('symbol').resample("D").last().dropna(how='all')
    daily_df.index = daily_df.index.droplevel()
    daily_df.sort_index(inplace=True)
    try:
        daily_df['diff'] = daily_df['close'].diff()
    except:
        daily_df['diff'] = daily_df['last'].diff()

    # build flags
    flags = _continous_contract_flags(daily_df)

    # resample back to original
    if "K" in resolution or "V" in resolution or "S" in resolution:
        flags = flags.resample('S').last().ffill().loc[df.index.unique()].ffill()
    else:
        flags = flags.resample('T').last().ffill().loc[df.index.unique()].ffill()
    flags['datetime'] = flags.index

    # build contract
    contract = pd.merge(df, flags, how='left', on=['datetime', 'symbol']).ffill()
    contract.set_index('datetime', inplace=True)

    contract = contract[contract.expiry_y==contract.expiry_x]
    contract['expiry'] = contract['expiry_y']
    contract.drop(['expiry_y', 'expiry_x'], axis=1, inplace=True)

    try:
        contract['open']   = contract['open']+contract['gap']
        contract['high']   = contract['high']+contract['gap']
        contract['low']    = contract['low']+contract['gap']
        contract['close']  = contract['close']+contract['gap']
        # contract['volume'] = df['volume'].resample("D").sum()
    except:
        contract['last']  = contract['last']+contract['gap']

    contract.drop(['gap'], axis=1, inplace=True)

    return contract


# -------------------------------------------
def get_active_contract(symbol, url=None, n=1):

    # cell content reader
    def read_cells(row):
        cells = row.findAll('th')+row.findAll('td')
        return [cells[0].text.strip(), '', cells[7].text.strip().replace(',','')]

    def get_contracts(url):

        html = requests.get(url, timeout=5)
        html = bs(html.text, 'html.parser')

        data = html.find('table', attrs={'id':'settlementsFuturesProductTable'})

        rows = data.findAll('tr')
        text = '\n'.join(map(lambda row: ",".join(read_cells(row)), rows[2:]))

        # # Convert to DataFrame
        df = pd.read_csv(StringIO(text), names=['_', 'expiry', 'volume'], index_col=['_'], parse_dates=['_'])
        df.index = df.index.str.replace('JLY', 'JUL')
        for index, row in df.iterrows():
            try: df.loc[index, 'expiry'] = parse_date(index).strftime('%Y%m')
            except: pass

        # remove duplidates
        try:
            df = df.reset_index().drop_duplicates(subset=['_', 'volume'], keep='last')
        except:
            df = df.reset_index().drop_duplicates(subset=['_', 'volume'], take_last=True)

        df.drop('_', axis=1, inplace=True)

        return df[:13].dropna()


    if url is None:
        try: url = _get_futures_url(symbol, 'quotes_settlements_futures')
        except: pass

    try:
        c = get_contracts(url)
        if tools.after_third_friday():
            c = c[c.expiry!=datetime.datetime.now().strftime('%Y%m')]

        # based on volume
        if len(c[c.volume>100].index):
            return c.sort_values(by=['volume', 'expiry'], ascending=False)[:n]['expiry'].values[0]
        else:
            # based on date
            return c[:1]['expiry'].values[0]
    except:
        if tools.after_third_friday():
            return (datetime.datetime.now()+(datetime.timedelta(365/12)*2)).strftime('%Y%m')
        else:
            return (datetime.datetime.now()+datetime.timedelta(365/12)).strftime('%Y%m')


# -------------------------------------------
def get_contract_ticksize(symbol, fallback=0.01, ttl=84600):

    cache_file = tempfile.gettempdir()+"/ticksizes.pkl"
    used_fallback = False

    if os.path.exists(cache_file):
        df = pd.read_pickle(cache_file)
        if (int(time.time()) - int(os.path.getmtime(cache_file))) < ttl:
            filtered = df[df['symbol']==symbol]
            if len(filtered.index) > 0:
                return float(filtered['ticksize'].values[0])

    # continue...

    try:
        url = _get_futures_url(symbol, 'contract_specifications')
    except:
        return fallback

    html = requests.get(url, timeout=5)
    html = bs(html.text.lower(), 'html.parser')

    html = bs(requests.get(url).text.lower(), 'html.parser')
    try:
        ticksize_text = html.text.split('minimum price fluctuation')[1].strip()
        if ticksize_text.find("$") > 1:
            ticksize_text = ticksize_text.split('$')[0]
        else:
            ticksize_text = ticksize_text.split(' ')[0]
        if "1/" in ticksize_text:
            ticksize_text = ticksize_text.split("1/")[1].split(" ")[0]
            ticksize = 1/float(re.compile(r'[^\d.]+').sub('', ticksize_text))
        else:
            ticksize = float(re.compile(r'[^\d.]+').sub('', ticksize_text))

    except:
        ticksize = fallback
        used_fallback = True

    symdf = pd.DataFrame(index=[0], data={'symbol':symbol, 'ticksize':ticksize})
    if os.path.exists(cache_file):
        df = df[df['symbol']!=symbol].append(symdf[['symbol', 'ticksize']])
    else:
        df = symdf

    # save if fallback wasn't used
    if not used_fallback:
        df.to_pickle(cache_file)
        tools.chmod(cache_file)

    return float(ticksize)


# -------------------------------------------
def get_ib_futures(symbol=None, exchange=None, ttl=86400):

    cache_file = tempfile.gettempdir()+"/futures_spec.pkl"

    if os.path.exists(cache_file):
        if (int(time.time()) - int(os.path.getmtime(cache_file))) < ttl:
            df = pd.read_pickle(cache_file)

            if symbol is not None:
                if exchange is None:
                    return df[df['symbol']==symbol].to_dict(orient='records')[0]

                return df[
                    (df['exchange']==exchange) & (df['symbol']==symbol)
                ].to_dict(orient='records')[0]

            return df


    # else: fetch new...

    html = requests.get('https://www.interactivebrokers.com/en/index.php?f=marginnew&p=fut')

    # Parse HTML using BeautifulSoup
    html = bs(html.text, 'html.parser')

    records = []

    def grab_row(row, what='td'):
        row_data = []
        cells = row.findAll(what, text=True)
        for cell in cells:
            row_data.append(cell.text)

        return ",".join(row_data)

    divs = html.findAll('div', attrs={'class':'table-responsive'})

    for div in divs:
        tables = div.findAll('table');
        for table in tables:
            rows = table.findAll('tr');
            for row in rows:
                records.append(grab_row(row, 'td'))


    text = '\n'.join( filter(None, records) )

    df = pd.read_csv( StringIO(text), names=['exchange','symbol','description','class',
                                             'intraday_initial','intraday_maintenance',
                                             'overnight_initial','overnight_maintenance',
                                             'currency','has_options'] )

    # fix data
    df['intraday_initial'] = pd.to_numeric(df['intraday_initial'], errors='coerce')
    df['intraday_maintenance'] = pd.to_numeric(df['intraday_maintenance'], errors='coerce')
    df['overnight_initial'] = pd.to_numeric(df['overnight_initial'], errors='coerce')
    df['overnight_maintenance'] = pd.to_numeric(df['overnight_maintenance'], errors='coerce')

    df['currency'].fillna("USD", inplace=True)
    df['has_options'] = np.where(df['has_options']=='No', False, True)

    df.dropna(how='all', inplace=True)

    # output
    df.to_pickle(cache_file)
    tools.chmod(cache_file)

    if symbol is not None:
        if exchange is None:
            return df[df['symbol']==symbol].to_dict(orient='records')[0]

        return df[
            (df['exchange']==exchange) & (df['symbol']==symbol)
        ].to_dict(orient='records')[0]

    return df


# -------------------------------------------
def _get_futures_url(symbol, page):
    global futures_contracts
    try:
        return futures_contracts[symbol.upper()]['base_url'].replace('{}', page)
    except:
        return None

futures_contracts = {
    "GE": {
        "symbol": "GE",
        "product": "Eurodollar Futures",
        "group": "interest-rates",
        "base_url": "http://www.cmegroup.com/trading/interest-rates/stir/eurodollar_{}.html"
    },
    "N9L": {
        "symbol": "N9L",
        "product": "PJM Western Hub Real-Time Off-Peak Calendar-Month 5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/pjm-western-hub-off-peak-calendar-month-real-time-lmp-swap-futures_{}.html"
    },
    "ES": {
        "symbol": "ES",
        "product": "E-mini S&P 500 Futures",
        "group": "equity",
        "base_url": "http://www.cmegroup.com/trading/equity-index/us-index/e-mini-sandp500_{}.html"
    },
    "ZN": {
        "symbol": "ZN",
        "product": "10-Year T-Note Futures",
        "group": "interest-rates",
        "base_url": "http://www.cmegroup.com/trading/interest-rates/us-treasury/10-year-us-treasury-note_{}.html"
    },
    "ZF": {
        "symbol": "ZF",
        "product": "5-Year T-Note Futures",
        "group": "interest-rates",
        "base_url": "http://www.cmegroup.com/trading/interest-rates/us-treasury/5-year-us-treasury-note_{}.html"
    },
    "CL": {
        "symbol": "CL",
        "product": "Crude Oil Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/crude-oil/light-sweet-crude_{}.html"
    },
    "NN": {
        "symbol": "NN",
        "product": "Henry Hub Natural Gas Last Day Financial Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/henry-hub-natural-gas-swap-futures-financial_{}.html"
    },
    "ZC": {
        "symbol": "ZC",
        "product": "Corn Futures",
        "group": "agricultural",
        "base_url": "http://www.cmegroup.com/trading/agricultural/grain-and-oilseed/corn_{}.html"
    },
    "E4L": {
        "symbol": "E4L",
        "product": "PJM Western Hub Day-Ahead Off-Peak Calendar-Month 5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/pjm-western-hub-off-peak-calendar-month-day-ahead-lmp-swap-futures_{}.html"
    },
    "ZT": {
        "symbol": "ZT",
        "product": "2-Year T-Note Futures",
        "group": "interest-rates",
        "base_url": "http://www.cmegroup.com/trading/interest-rates/us-treasury/2-year-us-treasury-note_{}.html"
    },
    "NG": {
        "symbol": "NG",
        "product": "Henry Hub Natural Gas Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/natural-gas_{}.html"
    },
    "V3L": {
        "symbol": "V3L",
        "product": "PJM AEP Dayton Hub Real-Time Off-Peak Calendar-Month 5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/pjm-ad-hub-5-mw-off-peak-calendar-month-real-time-swap-futures_{}.html"
    },
    "B6L": {
        "symbol": "B6L",
        "product": "PJM Northern Illinois Hub Real-Time Off-Peak Calendar-Month 5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/pjm-ni-hub-5-mw-real-time-off-peak-futures_{}.html"
    },
    "ZQ": {
        "symbol": "ZQ",
        "product": "30 Day Federal Funds Futures",
        "group": "interest-rates",
        "base_url": "http://www.cmegroup.com/trading/interest-rates/stir/30-day-federal-fund_{}.html"
    },
    "ZS": {
        "symbol": "ZS",
        "product": "Soybean Futures",
        "group": "agricultural",
        "base_url": "http://www.cmegroup.com/trading/agricultural/grain-and-oilseed/soybean_{}.html"
    },
    "EJL": {
        "symbol": "EJL",
        "product": "MISO Indiana Hub (formerly Cinergy Hub) Real-Time Off-Peak Calendar-Month 5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/cinergy-hub-5-mw-off-peak-calendar-month-real-time-swap-futures_{}.html"
    },
    "L3L": {
        "symbol": "L3L",
        "product": "PJM Northern Illinois Hub Day-Ahead Off-Peak Calendar-Month 5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/pjm-northern-illinois-off-peak-calendar-month-day-ahead-swap-futures_{}.html"
    },
    "GC": {
        "symbol": "GC",
        "product": "Gold Futures",
        "group": "metals",
        "base_url": "http://www.cmegroup.com/trading/metals/precious/gold_{}.html"
    },
    "UB": {
        "symbol": "UB",
        "product": "Ultra U.S. Treasury Bond Futures",
        "group": "interest-rates",
        "base_url": "http://www.cmegroup.com/trading/interest-rates/us-treasury/ultra-t-bond_{}.html"
    },
    "ZB": {
        "symbol": "ZB",
        "product": "U.S. Treasury Bond Futures",
        "group": "interest-rates",
        "base_url": "http://www.cmegroup.com/trading/interest-rates/us-treasury/30-year-us-treasury-bond_{}.html"
    },
    "ZW": {
        "symbol": "ZW",
        "product": "Chicago SRW Wheat Futures",
        "group": "agricultural",
        "base_url": "http://www.cmegroup.com/trading/agricultural/grain-and-oilseed/wheat_{}.html"
    },
    "D2L": {
        "symbol": "D2L",
        "product": "NYISO Zone G Day-Ahead Off-Peak Calendar-Month 5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/nyiso-zone-g-5-mw-off-peak-day-ahead-futures_{}.html"
    },
    "6E": {
        "symbol": "6E",
        "product": "Euro FX Futures",
        "group": "fx",
        "base_url": "http://www.cmegroup.com/trading/fx/g10/euro-fx_{}.html"
    },
    "RB": {
        "symbol": "RB",
        "product": "RBOB Gasoline Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/rbob-gasoline_{}.html"
    },
    "ZM": {
        "symbol": "ZM",
        "product": "Soybean Meal Futures",
        "group": "agricultural",
        "base_url": "http://www.cmegroup.com/trading/agricultural/grain-and-oilseed/soybean-meal_{}.html"
    },
    "HO": {
        "symbol": "HO",
        "product": "NY Harbor ULSD Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/heating-oil_{}.html"
    },
    "ZL": {
        "symbol": "ZL",
        "product": "Soybean Oil Futures",
        "group": "agricultural",
        "base_url": "http://www.cmegroup.com/trading/agricultural/grain-and-oilseed/soybean-oil_{}.html"
    },
    "H2L": {
        "symbol": "H2L",
        "product": "ISO New England Mass Hub Day-Ahead Off-Peak Calendar-Month 5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/nepool-internal-hub-5-mw-off-peak-calendar-month-day-ahead-swap-futures_{}.html"
    },
    "NPG": {
        "symbol": "NPG",
        "product": "Henry Hub Natural Gas Penultimate Financial Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/natural-gas-penultimate-swap-financial_{}.html"
    },
    "K2L": {
        "symbol": "K2L",
        "product": "MISO Indiana Hub (formerly Cinergy Hub) Day-Ahead Off-Peak Calendar-Month 5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/miso-cinergy-hub-5-mw-off-peak-day-ahead-swap-futures_{}.html"
    },
    "HH": {
        "symbol": "HH",
        "product": "Natural Gas (Henry Hub) Last-day Financial Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/natural-gas-last-day_{}.html"
    },
    "K4L": {
        "symbol": "K4L",
        "product": "NYISO Zone A Day-Ahead Off-Peak Calendar-Month 5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/nyiso-zone-a-5-mw-off-peak-calendar-month-day-ahead-lbmp-swap-futures_{}.html"
    },
    "LE": {
        "symbol": "LE",
        "product": "Live Cattle Futures",
        "group": "agricultural",
        "base_url": "http://www.cmegroup.com/trading/agricultural/livestock/live-cattle_{}.html"
    },
    "WOL": {
        "symbol": "WOL",
        "product": "PJM Western Hub Real-Time Off-Peak Calendar-Day 5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/pjm-western-hub-real-time-off-peak-calendar-day-25-mw_{}.html"
    },
    "AD9": {
        "symbol": "AD9",
        "product": "PJM ComEd Zone 5 MW Off-Peak Calendar-Month Day-Ahead LMP Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/pjm-comed-5-mw-off-peak-calendar-month-day-ahead-lmp-swap-futures_{}.html"
    },
    "HE": {
        "symbol": "HE",
        "product": "Lean Hog Futures",
        "group": "agricultural",
        "base_url": "http://www.cmegroup.com/trading/agricultural/livestock/lean-hogs_{}.html"
    },
    "6B": {
        "symbol": "6B",
        "product": "British Pound Futures",
        "group": "fx",
        "base_url": "http://www.cmegroup.com/trading/fx/g10/british-pound_{}.html"
    },
    "KE": {
        "symbol": "KE",
        "product": "KC HRW Wheat Futures",
        "group": "agricultural",
        "base_url": "http://www.cmegroup.com/trading/agricultural/grain-and-oilseed/kc-wheat_{}.html"
    },
    "NQ": {
        "symbol": "NQ",
        "product": "E-mini NASDAQ 100 Futures",
        "group": "equity",
        "base_url": "http://www.cmegroup.com/trading/equity-index/us-index/e-mini-nasdaq-100_{}.html"
    },
    "SI": {
        "symbol": "SI",
        "product": "Silver Futures",
        "group": "metals",
        "base_url": "http://www.cmegroup.com/trading/metals/precious/silver_{}.html"
    },
    "HOA": {
        "symbol": "HOA",
        "product": "MISO Michigan Hub 5 MW Off-Peak Calendar-Month Day-Ahead Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/midwest-iso-michigan-hub-5-mw-off-peak-calendar-month-day-ahead-swap-futures_{}.html"
    },
    "AL1": {
        "symbol": "AL1",
        "product": "PJM Western Hub Peak Calendar-Month Real-Time LMP Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/pjm-western-hub-peak-calendar-month-real-time-lmp_{}.html"
    },
    "HG": {
        "symbol": "HG",
        "product": "Copper Futures",
        "group": "metals",
        "base_url": "http://www.cmegroup.com/trading/metals/base/copper_{}.html"
    },
    "R7L": {
        "symbol": "R7L",
        "product": "PJM AEP Dayton Hub Day-Ahead Off-Peak Calendar-Month 5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/pjm-aep-dayton-hub-off-peak-calendar-month-day-ahead-lmp-swap-futures_{}.html"
    },
    "6J": {
        "symbol": "6J",
        "product": "Japanese Yen Futures",
        "group": "fx",
        "base_url": "http://www.cmegroup.com/trading/fx/g10/japanese-yen_{}.html"
    },
    "BZ": {
        "symbol": "BZ",
        "product": "Brent Last Day Financial Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/crude-oil/brent-crude-oil-last-day_{}.html"
    },
    "TN": {
        "symbol": "TN",
        "product": "Ultra 10-Year U.S. Treasury Note Futures",
        "group": "interest-rates",
        "base_url": "http://www.cmegroup.com/trading/interest-rates/us-treasury/ultra-10-year-us-treasury-note_{}.html"
    },
    "AW6": {
        "symbol": "AW6",
        "product": "PJM PSEG Zone Off-Peak Calendar-Month Day-Ahead LMP Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/pjm-pseg-zone-off-peak-calendar-month-day-ahead-lmp-swap-futures_{}.html"
    },
    "B0": {
        "symbol": "B0",
        "product": "Mont Belvieu LDH Propane (OPIS) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/petrochemicals/mont-belvieu-propane-5-decimals-swap_{}.html"
    },
    "D4L": {
        "symbol": "D4L",
        "product": "NYISO Zone J Day-Ahead Off-Peak Calendar-Month 5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/nyiso-zone-j-5-mw-off-peak-cal-mon-day-ahead-lbmp-swap-futures_{}.html"
    },
    "HP": {
        "symbol": "HP",
        "product": "Natural Gas (Henry Hub) Penultimate Financial Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/natural-gas-penultimate_{}.html"
    },
    "CSX": {
        "symbol": "CSX",
        "product": "WTI Financial Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/crude-oil/west-texas-intermediate-wti-crude-oil-calendar-swap-futures_{}.html"
    },
    "MTF": {
        "symbol": "MTF",
        "product": "Coal (API2) CIF ARA (ARGUS-McCloskey) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/coal/coal-api-2-cif-ara-argus-mccloskey_{}.html"
    },
    "6C": {
        "symbol": "6C",
        "product": "Canadian Dollar Futures",
        "group": "fx",
        "base_url": "http://www.cmegroup.com/trading/fx/g10/canadian-dollar_{}.html"
    },
    "YM": {
        "symbol": "YM",
        "product": "E-mini Dow ($5) Futures",
        "group": "equity",
        "base_url": "http://www.cmegroup.com/trading/equity-index/us-index/e-mini-dow_{}.html"
    },
    "AU5": {
        "symbol": "AU5",
        "product": "ISO New England Rhode Island Zone 5 MW Off-Peak Calendar-Month Day-Ahead LMP Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/nepool-rhode-island-5-mw-off-peak-calendar-month-day-ahead-swap-futures_{}.html"
    },
    "6M": {
        "symbol": "6M",
        "product": "Mexican Peso Futures",
        "group": "fx",
        "base_url": "http://www.cmegroup.com/trading/fx/emerging-market/mexican-peso_{}.html"
    },
    "OFF": {
        "symbol": "OFF",
        "product": "Ontario Off-Peak Calendar-Month Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/ontario-off-peak-calendar-month-swap-futures_{}.html"
    },
    "SP": {
        "symbol": "SP",
        "product": "S&P 500 Futures",
        "group": "equity",
        "base_url": "http://www.cmegroup.com/trading/equity-index/us-index/sandp-500_{}.html"
    },
    "NR": {
        "symbol": "NR",
        "product": "Rockies Natural Gas (Platts IFERC) Basis Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/northwest-pipeline-rockies-natural-gas-basis-swap-futures-platts-iferc_{}.html"
    },
    "EMD": {
        "symbol": "EMD",
        "product": "E-mini S&P MidCap 400 Futures",
        "group": "equity",
        "base_url": "http://www.cmegroup.com/trading/equity-index/us-index/e-mini-sandp-midcap-400_{}.html"
    },
    "6A": {
        "symbol": "6A",
        "product": "Australian Dollar Futures",
        "group": "fx",
        "base_url": "http://www.cmegroup.com/trading/fx/g10/australian-dollar_{}.html"
    },
    "NIY": {
        "symbol": "NIY",
        "product": "Nikkei/Yen Futures",
        "group": "equity",
        "base_url": "http://www.cmegroup.com/trading/equity-index/international-index/nikkei-225-yen_{}.html"
    },
    "AC0": {
        "symbol": "AC0",
        "product": "Mont Belvieu Ethane (OPIS) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/petrochemicals/mont-belvieu-ethane-opis-5-decimals-swap_{}.html"
    },
    "PWL": {
        "symbol": "PWL",
        "product": "PJM Western Hub  Day-Ahead Off-Peak Calendar-Day 5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/pjm-western-hub-day-ahead-off-peak-calendar-day-25-mw_{}.html"
    },
    "PL": {
        "symbol": "PL",
        "product": "Platinum Futures",
        "group": "metals",
        "base_url": "http://www.cmegroup.com/trading/metals/precious/platinum_{}.html"
    },
    "AA3": {
        "symbol": "AA3",
        "product": "NYISO Zone C 5 MW Off-Peak Calendar-Month Day-Ahead LBMP Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/nyiso-zone-c-5-mw-off-peak-calendar-month-day-ahead-lbmp-swap-futures_{}.html"
    },
    "BK": {
        "symbol": "BK",
        "product": "WTI-Brent Financial Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/crude-oil/wti-brent-ice-calendar-swap-futures_{}.html"
    },
    "J4L": {
        "symbol": "J4L",
        "product": "PJM Western Hub Day-Ahead Peak Calendar-Month 5 MW Futures  ",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/pjm-western-hub-peak-calendar-month-day-ahead-lmp-swap-futures_{}.html"
    },
    "NOI": {
        "symbol": "NOI",
        "product": "PJM Northern Illinois Hub Real-Time Off-Peak Calendar-Day 5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/pjm-northern-illinois-hub-real-time-off-peak-calendar-day-25-mw_{}.html"
    },
    "LT": {
        "symbol": "LT",
        "product": "Gulf Coast ULSD (Platts) Up-Down Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/up-down-gulf-coast-ultra-low-sulfur-diesel-ulsd-vs-nymex-heating-oil-ho-spread-swap-futures_{}.html"
    },
    "AZ9": {
        "symbol": "AZ9",
        "product": "PJM AEP Dayton Hub 5MW Peak Calendar-Month Real-Time LMP Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/pjm-ad-hub-5-mw-peak-real-time-lmp-swap-futures_{}.html"
    },
    "A46": {
        "symbol": "A46",
        "product": "PJM METED Zone Off-Peak Calendar-Month Day-Ahead LMP Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/pjm-meted-zone-off-peak-calendar-month-day-ahead-lmp-swap-futures_{}.html"
    },
    "PD": {
        "symbol": "PD",
        "product": "NGPL TexOk Natural Gas (Platts IFERC) Basis Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/natural-gas-pipeline-texasoklahoma-natural-gas-basis-swap-futures-platts-iferc_{}.html"
    },
    "SDA": {
        "symbol": "SDA",
        "product": "S&P 500 Annual Dividend Index Futures",
        "group": "equity",
        "base_url": "http://www.cmegroup.com/trading/equity-index/us-index/sp-500-annual-dividend-index_{}.html"
    },
    "CU": {
        "symbol": "CU",
        "product": "Chicago Ethanol (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/ethanol/chicago-ethanol-platts-swap_{}.html"
    },
    "POL": {
        "symbol": "POL",
        "product": "PJM Northern Illinois Hub  Day-Ahead Off-Peak Calendar-Day 5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/pjm-northern-illinois-hub-day-ahead-off-peak-calendar-day-25-mw_{}.html"
    },
    "CIN": {
        "symbol": "CIN",
        "product": "CIG Rockies Natural Gas (Platts IFERC) Basis Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/cig-rocky-mountain-natural-gas-basis-swap-futures-platts-iferc_{}.html"
    },
    "EAF": {
        "symbol": "EAF",
        "product": "In Delivery Month European Union Allowance (EUA) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/emissions/in-delivery-month-european-union-allowance_{}.html"
    },
    "AH3": {
        "symbol": "AH3",
        "product": "MISO Indiana Hub (formerly Cinergy Hub) 5 Month Peak Calendar-Month Real-Time Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/cinergy-hub-5-mw-peak-real-time_{}.html"
    },
    "MFB": {
        "symbol": "MFB",
        "product": "Gulf Coast HSFO (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/gulf-coast-no-6-fuel-oil-30pct-sulfur-platts-swap_{}.html"
    },
    "AF2": {
        "symbol": "AF2",
        "product": "PJM JCPL Zone Off-Peak Calendar-Month Day-Ahead LMP Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/pjm-jcpl-zone-calendar-month-day-ahead-lmp-swap-futures_{}.html"
    },
    "6N": {
        "symbol": "6N",
        "product": "New Zealand Dollar Futures",
        "group": "fx",
        "base_url": "http://www.cmegroup.com/trading/fx/g10/new-zealand-dollar_{}.html"
    },
    "PGN": {
        "symbol": "PGN",
        "product": "Dominion, South Point Natural Gas (Platts IFERC) Basis Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/dominion-appalachia-natural-gas-basis-swap-futures-platts-iferc_{}.html"
    },
    "HB": {
        "symbol": "HB",
        "product": "Henry Hub Natural Gas (Platts IFERC) Basis Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/henry-hub-natural-gas-basis-swap-futures-platts-iferc_{}.html"
    },
    "PH": {
        "symbol": "PH",
        "product": "Panhandle Natural Gas (Platts IFERC) Basis Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/panhandle-natural-gas-basis-swap-futures-platts-iferc_{}.html"
    },
    "GIE": {
        "symbol": "GIE",
        "product": "S&P-GSCI ER Index Futures",
        "group": "agricultural",
        "base_url": "http://www.cmegroup.com/trading/agricultural/commodity-index/gsci-excess-return_{}.html"
    },
    "AOL": {
        "symbol": "AOL",
        "product": "PJM AEP Dayton Hub Real-Time Off-Peak Calendar-Day 5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/pjm-aep-dayton-hub-real-time-off-peak-calendar-day-25-mw_{}.html"
    },
    "AX1": {
        "symbol": "AX1",
        "product": "PJM AECO Zone Off-Peak Calendar-Month Day-Ahead LMP Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/pjm-aeco-zone-off-peak-calendar-month-day-ahead-lmp-swap-futures_{}.html"
    },
    "GF": {
        "symbol": "GF",
        "product": "Feeder Cattle Futures",
        "group": "agricultural",
        "base_url": "http://www.cmegroup.com/trading/agricultural/livestock/feeder-cattle_{}.html"
    },
    "NL": {
        "symbol": "NL",
        "product": "NGPL Mid-Con Natural Gas (Platts IFERC) Basis Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/natural-gas-pipeline-ngpl-midcontinent-basis-swap-futures-platts-iferc_{}.html"
    },
    "AL9": {
        "symbol": "AL9",
        "product": "ISO New England West Central Massachusetts Zone 5 MW Off-Peak Calendar-Month Day Ahead LMP Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/nepool-w-central-mass-zone-5-off-peak-mw-day-ahead-swap-futures_{}.html"
    },
    "AB3": {
        "symbol": "AB3",
        "product": "PJM Northern Illinois Hub 5 MW Peak Calendar-Month Real-Time LMP Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/pjm-northern-illinois-hub-5-mw-peak-real-time-calendar-month-lmp-swap-futures_{}.html"
    },
    "6R": {
        "symbol": "6R",
        "product": "Russian Ruble Futures",
        "group": "fx",
        "base_url": "http://www.cmegroup.com/trading/fx/emerging-market/russian-ruble_{}.html"
    },
    "ME": {
        "symbol": "ME",
        "product": "Gulf Coast Jet (Platts) Up-Down Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/gulf-coast-jet-fuel-vs-nymex-no-2-heating-oil-platts-spread-swap_{}.html"
    },
    "NJ": {
        "symbol": "NJ",
        "product": "San Juan Natural Gas (Platts IFERC) Basis Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/san-juan-basin-natural-gas-basis-swap-futures-platts-iferc_{}.html"
    },
    "AR3": {
        "symbol": "AR3",
        "product": "PJM BGE Zone Off-Peak Calendar-Month Day-Ahead LMP Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/pjm-bge-zone-off-peak-calendar-month-day-ahead-lmp-swap-futures_{}.html"
    },
    "6S": {
        "symbol": "6S",
        "product": "Swiss Franc Futures",
        "group": "fx",
        "base_url": "http://www.cmegroup.com/trading/fx/g10/swiss-franc_{}.html"
    },
    "AWJ": {
        "symbol": "AWJ",
        "product": "LLS (Argus) vs. WTI Financial Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/crude-oil/lls-crude-oil-argus-vs-wti-calendar-spread-swap-futures_{}.html"
    },
    "N3L": {
        "symbol": "N3L",
        "product": "PJM Northern Illinois Hub Day-Ahead LMP Peak Calendar-Month 5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/pjm-northern-illinois-hub-peak-calendar-month-day-ahead-swap-futures_{}.html"
    },
    "NKD": {
        "symbol": "NKD",
        "product": "Nikkei/USD Futures",
        "group": "equity",
        "base_url": "http://www.cmegroup.com/trading/equity-index/international-index/nikkei-225-dollar_{}.html"
    },
    "AF5": {
        "symbol": "AF5",
        "product": "PJM PPL Zone Off-Peak Calendar-Month Day-Ahead LMP Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/pjm-ppl-zone-off-peak-calendar-month-day-ahead-lmp-swap-futures_{}.html"
    },
    "XK": {
        "symbol": "XK",
        "product": "Mini Soybean Futures",
        "group": "agricultural",
        "base_url": "http://www.cmegroup.com/trading/agricultural/grain-and-oilseed/mini-sized-soybean_{}.html"
    },
    "TME": {
        "symbol": "TME",
        "product": "Dutch Natural Gas Calendar Month Future",
        "group": "products",
        "base_url": "http://www.cmegroup.com/trading/products/energy/natural-gas/dutch-natural-gas-calendar-month_{}.html"
    },
    "NHN": {
        "symbol": "NHN",
        "product": "Houston Ship Channel Natural Gas (Platts IFERC) Basis Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/houston-ship-channel-natural-gas-basis-swap-futures-platts-iferc_{}.html"
    },
    "TC": {
        "symbol": "TC",
        "product": "Columbia Gas TCO (Platts IFERC) Basis Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/tco-appalachia-natural-gas-basis-swap-futures-platts-iferc_{}.html"
    },
    "RP": {
        "symbol": "RP",
        "product": "Euro/British Pound Futures",
        "group": "fx",
        "base_url": "http://www.cmegroup.com/trading/fx/g10/euro-fx-british-pound_{}.html"
    },
    "TRZ": {
        "symbol": "TRZ",
        "product": "Transco Zone 4 Natural Gas (Platts IFERC) Basis Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/transco-zone-4-natural-gas-basis-swap-futures_{}.html"
    },
    "AUP": {
        "symbol": "AUP",
        "product": "Aluminum MW U.S. Transaction Premium Platts (25MT) Futures",
        "group": "metals",
        "base_url": "http://www.cmegroup.com/trading/metals/base/aluminum-mw-us-transaction-premium-platts-swap-futures_{}.html"
    },
    "5ZN": {
        "symbol": "5ZN",
        "product": "Columbia Gulf, Mainline Natural Gas (Platts IFERC) Basis Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/columbia-gulf-mainline-natural-gas-basis-swap-futures_{}.html"
    },
    "A58": {
        "symbol": "A58",
        "product": "NYISO Zone E 5 MW Off-Peak Calendar-Month Day-Ahead LBMP Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/nyiso-zone-e-5-mw-off-peak-calendar-month-day-ahead-lbmp-swap-futures_{}.html"
    },
    "DC": {
        "symbol": "DC",
        "product": "Class III Milk Futures",
        "group": "agricultural",
        "base_url": "http://www.cmegroup.com/trading/agricultural/dairy/class-iii-milk_{}.html"
    },
    "AD0": {
        "symbol": "AD0",
        "product": "Mont Belvieu Normal Butane (OPIS) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/petrochemicals/mont-belvieu-normal-butane-5-decimals-swap_{}.html"
    },
    "F1U": {
        "symbol": "F1U",
        "product": "5-Year USD Deliverable Interest Rate Swap Futures",
        "group": "interest-rates",
        "base_url": "http://www.cmegroup.com/trading/interest-rates/deliverable-swaps/5-year-deliverable-interest-rate-swap-futures_{}.html"
    },
    "ZAL": {
        "symbol": "ZAL",
        "product": "NYISO Zone A Day-Ahead Off-Peak Calendar-Day 5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/nyiso-zone-a-day-ahead-off-peak-calendar-day-25-mw_{}.html"
    },
    "FTQ": {
        "symbol": "FTQ",
        "product": "MISO Indiana Hub Real-Time Off-Peak Calendar-Month 5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/midwest-iso-indiana-hub-5-mw-off-peak-calendar-month-real-time-swap-futures_{}.html"
    },
    "CSC": {
        "symbol": "CSC",
        "product": "Cash-Settled Cheese Futures",
        "group": "agricultural",
        "base_url": "http://www.cmegroup.com/trading/agricultural/dairy/cheese_{}.html"
    },
    "6L": {
        "symbol": "6L",
        "product": "Brazilian Real Futures",
        "group": "fx",
        "base_url": "http://www.cmegroup.com/trading/fx/emerging-market/brazilian-real_{}.html"
    },
    "T3L": {
        "symbol": "T3L",
        "product": "NYISO Zone G Day-Ahead Peak Calendar-Month 5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/nyiso-zone-g-5-mw-peak-calendar-month-day-ahead-swap-futures_{}.html"
    },
    "T7K": {
        "symbol": "T7K",
        "product": "Gasoline Euro-bob Oxy NWE Barges (Argus) Crack Spread Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/gasoline-euro-bob-oxy-new-barges-crack-spread-swap-futures_{}.html"
    },
    "N1U": {
        "symbol": "N1U",
        "product": "10-Year USD Deliverable Interest Rate Swap Futures",
        "group": "interest-rates",
        "base_url": "http://www.cmegroup.com/trading/interest-rates/deliverable-swaps/10-year-deliverable-interest-rate-swap-futures_{}.html"
    },
    "GCU": {
        "symbol": "GCU",
        "product": "Gulf Coast HSFO (Platts) vs. European 3.5% Fuel Oil Barges FOB Rdam (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/gulf-coast-no6-fuel-oil-3pct-vs-european-3point5pct-fuel-oil-barges-fob-rdam-platts-swap-futures_{}.html"
    },
    "IDL": {
        "symbol": "IDL",
        "product": "ISO New England Mass Hub Day-Ahead Off-Peak Calendar-Day 5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/iso-new-england-mass-hub-day-ahead-off-peak-calendar-day-25-mw_{}.html"
    },
    "NX": {
        "symbol": "NX",
        "product": "Texas Eastern Zone M-3 Natural Gas (Platts IFERC) Basis Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/texas-eastern-zone-m-3-natural-gas-basis-swap-futures-platts-iferc_{}.html"
    },
    "XAP": {
        "symbol": "XAP",
        "product": "E-mini Consumer Staples Select Sector Futures",
        "group": "equity",
        "base_url": "http://www.cmegroup.com/trading/equity-index/select-sector-index/e-mini-consumer-staples-select-sector_{}.html"
    },
    "AU6": {
        "symbol": "AU6",
        "product": "ISO New England Mass Hub 5 MW Peak Calendar-Month Day-Ahead LMP Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/nepool-internal-hub-5-mw-peak-calendar-month-day-ahead-swap-futures_{}.html"
    },
    "MDD": {
        "symbol": "MDD",
        "product": "PJM ATSI Zone 5 MW Off-Peak Calendar-Month Day-Ahead Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/pjm-atsi-zone-5-mw-off-peak-calendar-month-day-ahead-swap-futures_{}.html"
    },
    "A1R": {
        "symbol": "A1R",
        "product": "Propane Non-LDH Mont Belvieu (OPIS) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/petrochemicals/propane-non-ldh-mt-belvieu-opis-swap_{}.html"
    },
    "AFF": {
        "symbol": "AFF",
        "product": "WTI Midland (Argus) vs. WTI Financial Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/crude-oil/wts-argus-vs-wti-calendar-spread-swap-futures_{}.html"
    },
    "<tr": {
        "symbol": "<tr",
        "product": "LOOP Crude Oil Storage Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/crude-oil/loop-crude-oil-storage_{}.html"
    },
    "PW": {
        "symbol": "PW",
        "product": "Enable Natural Gas (Platts IFERC) Basis Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/centerpoint-natural-gas-basis-swap-futures-platts-iferc_{}.html"
    },
    "PA": {
        "symbol": "PA",
        "product": "Palladium Futures",
        "group": "metals",
        "base_url": "http://www.cmegroup.com/trading/metals/precious/palladium_{}.html"
    },
    "GL": {
        "symbol": "GL",
        "product": "Columbia Gulf, Louisiana Natural Gas (Platts IFERC) Basis Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/columbia-gulf-onshore-natural-gas-basis-swap-futures-platts-iferc_{}.html"
    },
    "D7L": {
        "symbol": "D7L",
        "product": "PJM AEP Dayton Hub Day-Ahead LMP Peak Calendar-Month 5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/pjm-aep-dayton-hub-peak-calendar-month-day-ahead-lmp-swap-futures_{}.html"
    },
    "H5L": {
        "symbol": "H5L",
        "product": "MISO Indiana Hub (formerly Cinergy Hub) Day-Ahead Peak Calendar-Month 5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/cinergy-hub-5-mw-peak-calendar-month-day-ahead-swap-futures_{}.html"
    },
    "FTL": {
        "symbol": "FTL",
        "product": "MISO Indiana Hub Real-Time Off-Peak Calendar-Day 5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/midwest-iso-indiana-hub-5-mw-off-peak-calendar-day-real-time-swap-futures_{}.html"
    },
    "XAU": {
        "symbol": "XAU",
        "product": "E-mini Utilities Select Sector Futures",
        "group": "equity",
        "base_url": "http://www.cmegroup.com/trading/equity-index/select-sector-index/e-mini-utilities-select-sector_{}.html"
    },
    "TIO": {
        "symbol": "TIO",
        "product": "Iron Ore 62% Fe, CFR China (TSI) Futures",
        "group": "metals",
        "base_url": "http://www.cmegroup.com/trading/metals/ferrous/iron-ore-62pct-fe-cfr-china-tsi-swap-futures_{}.html"
    },
    "IN": {
        "symbol": "IN",
        "product": "Henry Hub Natural Gas (Platts Gas Daily/Platts IFERC) Index Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/henry-hub-natural-gas-index-swap-futures-platts-gas-daily-platts-iferc_{}.html"
    },
    "HRC": {
        "symbol": "HRC",
        "product": "U.S. Midwest Domestic Hot-Rolled Coil Steel (CRU) Index Futures",
        "group": "metals",
        "base_url": "http://www.cmegroup.com/trading/metals/ferrous/hrc-steel_{}.html"
    },
    "PEL": {
        "symbol": "PEL",
        "product": "PJM AEP Dayton Hub Day-Ahead Off-Peak Calendar-Day 5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/pjm-aep-dayton-hub-day-ahead-off-peak-calendar-day-25-mw_{}.html"
    },
    "FO": {
        "symbol": "FO",
        "product": "3.5% Fuel Oil Barges FOB Rdam (Platts) Crack Spread Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/northwest-europe-nwe-35pct-fuel-oil-rottderdam-crack-spread-swap_{}.html"
    },
    "TDE": {
        "symbol": "TDE",
        "product": "Dutch Natural Gas Daily Future",
        "group": "products",
        "base_url": "http://www.cmegroup.com/trading/products/energy/natural-gas/dutch-natural-gas-daily_{}.html"
    },
    "MFF": {
        "symbol": "MFF",
        "product": "Coal (API4) FOB Richards Bay (ARGUS-McCloskey) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/coal/coal-api-4-fob-richards-bay-argus-mccloskey_{}.html"
    },
    "AE5": {
        "symbol": "AE5",
        "product": "Argus LLS vs. WTI (Argus) Trade Month Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/crude-oil/argus-lls-vs-wti-argus-trade-month-swap-futures_{}.html"
    },
    "AW": {
        "symbol": "AW",
        "product": "Bloomberg Commodity Index Futures",
        "group": "agricultural",
        "base_url": "http://www.cmegroup.com/trading/agricultural/commodity-index/bloomberg-commodity-index_{}.html"
    },
    "GZ": {
        "symbol": "GZ",
        "product": "European Low Sulphur Gasoil Brent Crack Spread Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/european-gasoil-crack-spread-calendar-swap_{}.html"
    },
    "RBB": {
        "symbol": "RBB",
        "product": "RBOB Gasoline Brent Crack Spread Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/rbob-gasoline-vs-brent-crack-spread-swap-futures_{}.html"
    },
    "AP3": {
        "symbol": "AP3",
        "product": "ISO New England Connecticut Zone 5 MW Off-Peak Calendar-Month Day-Ahead LMP Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/nepool-connecticut-5-mw-off-peak-calendar-month-day-ahead-lmp-swap-futures_{}.html"
    },
    "A7Q": {
        "symbol": "A7Q",
        "product": "Mont Belvieu Natural Gasoline (OPIS) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/petrochemicals/mont-belvieu-natural-gasoline-5-decimal-opis-swap_{}.html"
    },
    "CY": {
        "symbol": "CY",
        "product": "Brent Financial Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/crude-oil/brent-ice-calendar-swap-futures_{}.html"
    },
    "NW": {
        "symbol": "NW",
        "product": "Waha Natural Gas (Platts IFERC) Basis Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/waha-texas-natural-gas-basis-swap-futures-platts-iferc_{}.html"
    },
    "HOB": {
        "symbol": "HOB",
        "product": "NY Harbor ULSD Brent Crack Spread Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/heating-oil-vs-brent-crack-spread-swap-futures_{}.html"
    },
    "AD8": {
        "symbol": "AD8",
        "product": "PJM ComEd Zone 5 MW Peak Calendar-Month Day-Ahead LMP Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/pjm-comed-5-mw-peak-calendar-month-day-ahead-lmp-swap-futures_{}.html"
    },
    "9FN": {
        "symbol": "9FN",
        "product": "Texas Gas, Zone 1 Natural Gas (Platts IFERC) Basis Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/texas-gas-zone-1-natural-gas-basis-swap-futures-platts-iferc_{}.html"
    },
    "A8K": {
        "symbol": "A8K",
        "product": "Conway Propane (OPIS) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/petrochemicals/conway-propane-opis-swap_{}.html"
    },
    "PM": {
        "symbol": "PM",
        "product": "Permian Natural Gas (Platts IFERC) Basis Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/el-paso-permian-basin-natural-gas-basis-swap-futures-platts-iferc_{}.html"
    },
    "ZGL": {
        "symbol": "ZGL",
        "product": "NYISO Zone G Day-Ahead Off-Peak Calendar-Day 5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/nyiso-zone-g-day-ahead-off-peak-calendar-day-25-mw_{}.html"
    },
    "RVR": {
        "symbol": "RVR",
        "product": "Gulf Coast Unl 87 Gasoline M2 (Platts) vs. RBOB Gasoline Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/gulf-coast-unl-87-gasoline-m2-platts-vs-rbob-spread-swap_{}.html"
    },
    "HWA": {
        "symbol": "HWA",
        "product": "MISO Michigan Hub 5 MW Peak Calendar-Month Day-Ahead Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/midwest-iso-michigan-hub-5-mw-peak-calendar-month-day-ahead-swap-futures_{}.html"
    },
    "TZ6": {
        "symbol": "TZ6",
        "product": "Transco Zone 6 Non-N.Y. Natural Gas (Platts IFERC) Basis Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/transco-zone-6-non-ny-platts-iferc-basis-swap_{}.html"
    },
    "MPX": {
        "symbol": "MPX",
        "product": "NY Harbor ULSD Financial Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/nymex-new-york-harbor-heating-oil-calendar-swap_{}.html"
    },
    "A4M": {
        "symbol": "A4M",
        "product": "NYISO Zone F 5 MW Off-Peak Calendar-Month Day-Ahead LBMP Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/nyiso-zone-f-5-mw-off-peak-calendar-month-day-ahead-lbmp-swap-futures_{}.html"
    },
    "A50": {
        "symbol": "A50",
        "product": "PJM PENELEC Zone Off-Peak Calendar-Month Day-Ahead LMP Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/pjm-penelec-zone-off-peak-calendar-month-day-ahead-lmp-swap-futures_{}.html"
    },
    "AHL": {
        "symbol": "AHL",
        "product": "NY Harbor ULSD Crack Spread Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/ny-harbor-heating-oil-crack-spread-calendar-swap_{}.html"
    },
    "WCC": {
        "symbol": "WCC",
        "product": "Canadian Heavy Crude Oil Index (Net Energy) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/crude-oil/canadian-heavy-crude-oil-net-energy-index-futures_{}.html"
    },
    "AYX": {
        "symbol": "AYX",
        "product": "Mars (Argus) vs. WTI Financial Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/crude-oil/mars-crude-oil-argus-vs-wti-calendar-spread-swap-futures_{}.html"
    },
    "RLX": {
        "symbol": "RLX",
        "product": "RBOB Gasoline Financial Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/rbob-calendar-swap-futures_{}.html"
    },
    "GD": {
        "symbol": "GD",
        "product": "S&P-GSCI Commodity Index Futures",
        "group": "agricultural",
        "base_url": "http://www.cmegroup.com/trading/agricultural/commodity-index/gsci_{}.html"
    },
    "D3L": {
        "symbol": "D3L",
        "product": "NYISO Zone J Day-Ahead Peak Calendar-Month 5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/nyiso-zone-j-5-mw-peak-calendar-month-day-ahead-lbmp-swap-futures_{}.html"
    },
    "RY": {
        "symbol": "RY",
        "product": "Euro/Japanese Yen Futures",
        "group": "fx",
        "base_url": "http://www.cmegroup.com/trading/fx/g10/euro-fx-japanese-yen_{}.html"
    },
    "CIL": {
        "symbol": "CIL",
        "product": "Canadian Light Sweet Oil (Net Energy) Index Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/crude-oil/canadian-light-sweet-oil-net-energy-index-futures_{}.html"
    },
    "RF": {
        "symbol": "RF",
        "product": "Euro/Swiss Franc Futures",
        "group": "fx",
        "base_url": "http://www.cmegroup.com/trading/fx/g10/euro-fx-swiss-franc_{}.html"
    },
    "K3L": {
        "symbol": "K3L",
        "product": "NYISO Zone A Day-Ahead Peak Calendar-Month 5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/nyiso-zone-a-5-mw-peak-calendar-month-day-ahead-lbmp-swap-futures_{}.html"
    },
    "FAL": {
        "symbol": "FAL",
        "product": "MISO Indiana Hub Day-Ahead Off-Peak Calendar-Day 5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/midwest-iso-indiana-hub-5-mw-off-peak-calendar-day-day-ahead-swap-futures_{}.html"
    },
    "NKN": {
        "symbol": "NKN",
        "product": "Sumas Natural Gas (Platts IFERC) Basis Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/sumas-natural-gas-basis-swap-futures-platts-iferc_{}.html"
    },
    "NFN": {
        "symbol": "NFN",
        "product": "MichCon Natural Gas (Platts IFERC) Basis Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/michcon-natural-gas-basis-swap-futures-platts-iferc_{}.html"
    },
    "SGB": {
        "symbol": "SGB",
        "product": "Singapore Gasoil (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/singapore-gasoil-swap-futures_{}.html"
    },
    "AYV": {
        "symbol": "AYV",
        "product": "Mars (Argus) vs. WTI Trade Month Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/crude-oil/mars-crude-oil-argus-vs-wti-trade-month-spread-swap-futures_{}.html"
    },
    "IX": {
        "symbol": "IX",
        "product": "TETCO M-3 Natural Gas (Platts Gas Daily/Platts IFERC) Index Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/tetco-m-3-natural-gas-index-swap-futures-platts-gas-daily-platts-iferc_{}.html"
    },
    "ZO": {
        "symbol": "ZO",
        "product": "Oats Futures",
        "group": "agricultural",
        "base_url": "http://www.cmegroup.com/trading/agricultural/grain-and-oilseed/oats_{}.html"
    },
    "OOD": {
        "symbol": "OOD",
        "product": "Ontario Off-Peak Calendar-Day Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/ontario-off-peak-calendar-day-swap-futures_{}.html"
    },
    "MEO": {
        "symbol": "MEO",
        "product": "Mini Gasoline Euro-bob Oxy NWE Barges (Argus) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/mini-gasoline-euro-bob-oxy-argus-new-barges-swap-futures_{}.html"
    },
    "AI6": {
        "symbol": "AI6",
        "product": "ERCOT North 345 kV Hub 5 MW Off-Peak Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/ercot-north-zone-mcpe-5-mw-off-peak-swap-futures_{}.html"
    },
    "WTT": {
        "symbol": "WTT",
        "product": "WTI Midland (Argus) vs. WTI Trade Month Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/crude-oil/wti-midland-argus-vs-wti-trade-month_{}.html"
    },
    "XAI": {
        "symbol": "XAI",
        "product": "E-mini Industrial Select Sector Futures",
        "group": "equity",
        "base_url": "http://www.cmegroup.com/trading/equity-index/select-sector-index/e-mini-industrial-select-sector_{}.html"
    },
    "AFY": {
        "symbol": "AFY",
        "product": "Dated Brent (Platts) to Frontline Brent Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/crude-oil/dated-to-frontline-brent-crude-oil-swap-futures_{}.html"
    },
    "ZR": {
        "symbol": "ZR",
        "product": "Rough Rice Futures",
        "group": "agricultural",
        "base_url": "http://www.cmegroup.com/trading/agricultural/grain-and-oilseed/rough-rice_{}.html"
    },
    "XAY": {
        "symbol": "XAY",
        "product": "E-mini Consumer Discretionary Select Sector Futures",
        "group": "equity",
        "base_url": "http://www.cmegroup.com/trading/equity-index/select-sector-index/e-mini-consumer-discretionary-select-sector_{}.html"
    },
    "XC": {
        "symbol": "XC",
        "product": "Mini-Corn Futures",
        "group": "agricultural",
        "base_url": "http://www.cmegroup.com/trading/agricultural/grain-and-oilseed/mini-sized-corn_{}.html"
    },
    "N1B": {
        "symbol": "N1B",
        "product": "Singapore Mogas 92 Unleaded (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/singapore-mogas-92-unleaded-platts-swap-futures_{}.html"
    },
    "JML": {
        "symbol": "JML",
        "product": "PJM Western Hub Real-Time Peak Calendar-Month 2.5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/pjm-peak-calendar-month-lmp-swap-futures_{}.html"
    },
    "RX": {
        "symbol": "RX",
        "product": "Dow Jones Real Estate Futures",
        "group": "equity",
        "base_url": "http://www.cmegroup.com/trading/equity-index/us-index/dow-jones-rei_{}.html"
    },
    "EN": {
        "symbol": "EN",
        "product": "European Naphtha (Platts) Crack Spread Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/european-naphtha-crack-spread-swap_{}.html"
    },
    "Q9": {
        "symbol": "Q9",
        "product": "Florida Gas, Zone 3 Natural Gas (Platts Gas Daily/Platts IFERC) Index Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/florida-gas-zone-3-natural-gas-index-swap-futures-platts-gas-dailyplatts-iferc_{}.html"
    },
    "DIH": {
        "symbol": "DIH",
        "product": "Dominion, South Point Natural Gas (Platts Gas Daily/Platts IFERC) Index Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/dominion-natural-gas-app-index-swap-futures-platts-gas-daily-platts-iferc_{}.html"
    },
    "AW4": {
        "symbol": "AW4",
        "product": "PJM APS Zone Off-Peak Calendar-Month Day-Ahead LMP Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/pjm-aps-zone-off-peak-calendar-month-day-ahead-lmp-swap-futures_{}.html"
    },
    "CZN": {
        "symbol": "CZN",
        "product": "Transco Zone 3 Natural Gas (Platts IFERC) Basis Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/transco-zone-3-natural-gas-basis-swap-futures-platts-iferc_{}.html"
    },
    "JDL": {
        "symbol": "JDL",
        "product": "PJM Western Hub Real-Time Peak Calendar-Day 5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/pjm-calendar-daily-lmp-swap-futures_{}.html"
    },
    "UV": {
        "symbol": "UV",
        "product": "European 3.5% Fuel Oil Barges FOB Rdam (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/35pct-fuel-oil-swap-rotterdam-platts_{}.html"
    },
    "SE": {
        "symbol": "SE",
        "product": "Singapore Fuel Oil 380 cst (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/singapore-380cst-fuel-oil-platts-swap-futures_{}.html"
    },
    "MGH": {
        "symbol": "MGH",
        "product": "Gulf Coast HSFO (Platts) Crack Spread Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/gulf-coast-no-6-fuel-oil-platts-crack-swap_{}.html"
    },
    "BB": {
        "symbol": "BB",
        "product": "Brent Crude Oil Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/crude-oil/brent-crude-oil_{}.html"
    },
    "A0D": {
        "symbol": "A0D",
        "product": "Mini European 3.5% Fuel Oil Barges FOB Rdam (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/mini-european-35pct-fuel-oil-platts-barges-fob-rdam-swap-futures_{}.html"
    },
    "AU4": {
        "symbol": "AU4",
        "product": "ISO New England Rhode Island Zone 5 MW Peak Calendar-Month Day-Ahead LMP Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/nepool-rhode-island-5-mw-peak-calendar-month-day-ahead-swap-futures_{}.html"
    },
    "UX": {
        "symbol": "UX",
        "product": "UxC Uranium U3O8 Futures",
        "group": "metals",
        "base_url": "http://www.cmegroup.com/trading/metals/other/uranium_{}.html"
    },
    "VR": {
        "symbol": "VR",
        "product": "NY 1% Fuel Oil (Platts) vs. Gulf Coast HSFO (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/new-york-harbor-1pct-fuel-oil-vs-gulf-coast-3pct-fuel-oil-spread-swap_{}.html"
    },
    "AGA": {
        "symbol": "AGA",
        "product": "Singapore Gasoil (Platts) vs. Low Sulphur Gasoil Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/gasoil-arb-singapore-gasoil-platts-vs-ice-rdam-gasoil-swap_{}.html"
    },
    "B7H": {
        "symbol": "B7H",
        "product": "Gasoline Euro-bob Oxy NWE Barges (Argus) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/gasoline-euro-bob-oxy-new-barges-swap-futures_{}.html"
    },
    "AA6": {
        "symbol": "AA6",
        "product": "Group Three ULSD (Platts) vs. NY Harbor ULSD Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/group-three-ultra-low-sulfur-diesel-ulsd-platts-vs-heating-oil-spread-swap_{}.html"
    },
    "GY": {
        "symbol": "GY",
        "product": "Gulf Coast ULSD (Platts) Crack Spread Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/gulf-coast-ulsd-crack-spread-swap_{}.html"
    },
    "CB": {
        "symbol": "CB",
        "product": "Cash-settled Butter Futures",
        "group": "agricultural",
        "base_url": "http://www.cmegroup.com/trading/agricultural/dairy/cash-settled-butter_{}.html"
    },
    "GNF": {
        "symbol": "GNF",
        "product": "Non-fat Dry Milk Futures",
        "group": "agricultural",
        "base_url": "http://www.cmegroup.com/trading/agricultural/dairy/nonfat-dry-milk_{}.html"
    },
    "AEP": {
        "symbol": "AEP",
        "product": "Aluminium European Premium Duty-Unpaid (Metal Bulletin) Futures",
        "group": "metals",
        "base_url": "http://www.cmegroup.com/trading/metals/base/aluminium-european-premium-metal-bulletin-25mt-duty-unpaid_{}.html"
    },
    "MM": {
        "symbol": "MM",
        "product": "New York Harbor Residual Fuel 1.0% (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/new-york-harbor-residual-fuel-1pct-sulfur-platts-swap_{}.html"
    },
    "XAF": {
        "symbol": "XAF",
        "product": "E-mini Financial Select Sector Futures",
        "group": "equity",
        "base_url": "http://www.cmegroup.com/trading/equity-index/select-sector-index/e-mini-financial-select-sector_{}.html"
    },
    "XAV": {
        "symbol": "XAV",
        "product": "E-mini Health Care Select Sector Futures",
        "group": "equity",
        "base_url": "http://www.cmegroup.com/trading/equity-index/select-sector-index/e-mini-health-care-select-sector_{}.html"
    },
    "AL6": {
        "symbol": "AL6",
        "product": "PJM PSEG Zone Peak Calendar-Month Day-Ahead LMP 5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/pjm-pseg-zone-peak-calendar-month-day-ahead-lmp-swap-futures_{}.html"
    },
    "NEN": {
        "symbol": "NEN",
        "product": "ANR, Oklahoma Natural Gas (Platts IFERC) Basis Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/ANR-OK-Basis-Swap-Platts-IFERC-Futures_{}.html"
    },
    "EH": {
        "symbol": "EH",
        "product": "Ethanol Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/ethanol/cbot-ethanol_{}.html"
    },
    "MTS": {
        "symbol": "MTS",
        "product": "Mini Singapore Fuel Oil 380 cst (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/mini-singapore-fuel-oil-380-cst-platts-swap-futures_{}.html"
    },
    "WS": {
        "symbol": "WS",
        "product": "Crude Oil Financial Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/crude-oil/light-sweet-crude-cash-settled_{}.html"
    },
    "BOO": {
        "symbol": "BOO",
        "product": "3.5% Fuel Oil Barges FOB Rdam (Platts) Crack Spread (1000mt) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/35pct-fuel-oil-platts-barges-fob-rdam-crack-spread-1000mt-swap-futures_{}.html"
    },
    "AA5": {
        "symbol": "AA5",
        "product": "EIA Flat Tax On-Highway Diesel Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/eia-flat-tax-on-highway-diesel-swap_{}.html"
    },
    "NZN": {
        "symbol": "NZN",
        "product": "Transco Zone 6 Natural Gas (Platts IFERC) Basis Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/transco-zone-6-new-york-natural-gas-basis-swap-futures-platts-iferc_{}.html"
    },
    "M6E": {
        "symbol": "M6E",
        "product": "E-micro Euro/American Dollar Futures",
        "group": "fx",
        "base_url": "http://www.cmegroup.com/trading/fx/e-micros/e-micro-euro_{}.html"
    },
    "E7": {
        "symbol": "E7",
        "product": "E-mini Euro FX Futures",
        "group": "fx",
        "base_url": "http://www.cmegroup.com/trading/fx/g10/e-mini-euro-fx_{}.html"
    },
    "PF": {
        "symbol": "PF",
        "product": "Ventura Natural Gas (Platts IFERC) Basis Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/northern-natural-gas-ventura-iowa-basis-swap-futures-platts-iferc_{}.html"
    },
    "EVC": {
        "symbol": "EVC",
        "product": "Singapore Fuel Oil 380 cst (Platts) vs. European 3.5% Fuel Oil Barges FOB Rdam (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/singapore-fuel-oil-380-cst-platts-vs-european-35-fuel-oil-barges-fob-rdam-platts_{}.html"
    },
    "6Z": {
        "symbol": "6Z",
        "product": "South African Rand Futures",
        "group": "fx",
        "base_url": "http://www.cmegroup.com/trading/fx/emerging-market/south-african-rand_{}.html"
    },
    "XAK": {
        "symbol": "XAK",
        "product": "E-mini Technology Select Sector Futures",
        "group": "equity",
        "base_url": "http://www.cmegroup.com/trading/equity-index/select-sector-index/e-mini-technology-select-sector_{}.html"
    },
    "AKJ": {
        "symbol": "AKJ",
        "product": "NYISO Zone J Peak LBMP Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/nyiso-zone-j-peak-monthly-swap-futures_{}.html"
    },
    "MB": {
        "symbol": "MB",
        "product": "LOOP Gulf Coast Sour Crude Oil Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/crude-oil/gulf-coast-sour-crude-oil_{}.html"
    },
    "ALY": {
        "symbol": "ALY",
        "product": "Gulf Coast ULSD (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/gulf-coast-ultra-low-sulfur-diesel-usld-platts-calendar-swap_{}.html"
    },
    "LBS": {
        "symbol": "LBS",
        "product": "Random Length Lumber Futures",
        "group": "agricultural",
        "base_url": "http://www.cmegroup.com/trading/agricultural/lumber-and-pulp/random-length-lumber_{}.html"
    },
    "HGS": {
        "symbol": "HGS",
        "product": "Copper Financial Futures",
        "group": "metals",
        "base_url": "http://www.cmegroup.com/trading/metals/base/copper-calendar-swap-futures_{}.html"
    },
    "DY": {
        "symbol": "DY",
        "product": "Dry Whey Futures",
        "group": "agricultural",
        "base_url": "http://www.cmegroup.com/trading/agricultural/dairy/dry-whey_{}.html"
    },
    "MBR": {
        "symbol": "MBR",
        "product": "Mont Belvieu Ethylene (PCW) Financial Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/petrochemicals/mont-belvieu-ethylene-pcw-financial-swap-futures_{}.html"
    },
    "MBE": {
        "symbol": "MBE",
        "product": "Mont Belvieu Spot Ethylene In-Well Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/petrochemicals/mont-belvieu-spot-ethylene-in-well-futures_{}.html"
    },
    "AR6": {
        "symbol": "AR6",
        "product": "ISO New England West Central Massachusetts Zone 5 MW Peak Calendar-Month Day-Ahead LMP Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/nepool-w-central-mass-5-mw-peak-calendar-month-day-ahead-swap-futures_{}.html"
    },
    "GLI": {
        "symbol": "GLI",
        "product": "European Low Sulphur Gasoil (100mt) Bullet Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/european-gasoil-ice-futures_{}.html"
    },
    "EUS": {
        "symbol": "EUS",
        "product": "Euro / U.S. Dollar (EUR/USD) Physically Deliverable Future (CLS Eligible)",
        "group": "products",
        "base_url": "http://www.cmegroup.com/trading/products/fx/majors/eur-usd_{}.html"
    },
    "QM": {
        "symbol": "QM",
        "product": "E-mini Crude Oil Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/crude-oil/emini-crude-oil_{}.html"
    },
    "GDK": {
        "symbol": "GDK",
        "product": "Class IV Milk Futures",
        "group": "agricultural",
        "base_url": "http://www.cmegroup.com/trading/agricultural/dairy/class-iv-milk_{}.html"
    },
    "QP": {
        "symbol": "QP",
        "product": "Powder River Basin Coal (Platts OTC Broker Index) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/coal/western-rail-powder-river-basin-coal-swap-futures_{}.html"
    },
    "FOC": {
        "symbol": "FOC",
        "product": "NY 3.0% Fuel Oil (Platts) vs. Gulf Coast HSFO (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/ny-3pt0pct-fuel-oil-vs-gulf-coast-no-6-fuel-oil-3pt0pct-platts-swap-futures_{}.html"
    },
    "WPL": {
        "symbol": "WPL",
        "product": "PJM Western Hub Day-Ahead Peak Calendar-Day 5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/pjm-western-hub-day-ahead-peak-calendar-day-25-mw_{}.html"
    },
    "ABH": {
        "symbol": "ABH",
        "product": "NY Harbor ULSD Bullet Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/heating-oil-cash-settled_{}.html"
    },
    "XJT": {
        "symbol": "XJT",
        "product": "Houston Ship Channel Natural Gas (Platts IFERC) Fixed Price Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/houston-ship-channel-natural-gas-fixed-price-swap_{}.html"
    },
    "NIW": {
        "symbol": "NIW",
        "product": "NGPL Mid-Con Natural Gas (Platts Gas Daily/Platts IFERC) Index Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/ngpl-midcontinent-natural-gas-index-swap-futures-platts-gas-daily-platts-iferc_{}.html"
    },
    "OMM": {
        "symbol": "OMM",
        "product": "Ontario Peak Calendar-Month Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/ontario-peak-calendar-month-swap-futures_{}.html"
    },
    "HTT": {
        "symbol": "HTT",
        "product": "WTI Houston (Argus) vs. WTI Trade Month Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/crude-oil/wti-houston-argus-vs-wti-trade-month_{}.html"
    },
    "XN": {
        "symbol": "XN",
        "product": "SoCal Natural Gas (Platts IFERC) Fixed Price Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/socal-swap-platts-iferc-futures_{}.html"
    },
    "MNC": {
        "symbol": "MNC",
        "product": "Mini European Naphtha CIF NWE (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/mini-european-naphtha-platts-cif-nwe-swap-futures_{}.html"
    },
    "D1N": {
        "symbol": "D1N",
        "product": "Singapore Mogas 92 Unleaded (Platts) Brent Crack Spread Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/singapore-mogas-92-unleaded-platts-brent-crack-spread-swap-futures_{}.html"
    },
    "PTL": {
        "symbol": "PTL",
        "product": "MISO Indiana Hub Real-Time Peak Calendar-Day 5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/midwest-iso-indiana-hub-5-mw-peak-calendar-day-real-time-swap-futures_{}.html"
    },
    "A1L": {
        "symbol": "A1L",
        "product": "Gulf Coast ULSD (Platts) Up-Down BALMO Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/ulsd-up-down-balmo-calendar-swap-futures_{}.html"
    },
    "B4N": {
        "symbol": "B4N",
        "product": "Algonquin City-Gates Natural Gas (Platts IFERC) Basis Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/algonquin-citygates-natural-gas-basis-futures_{}.html"
    },
    "IY": {
        "symbol": "IY",
        "product": "Waha Natural Gas (Platts Gas Daily/Platts IFERC) Index Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/waha-natural-gas-index-swap-futures-platts-gas-daily-platts-iferc_{}.html"
    },
    "AUB": {
        "symbol": "AUB",
        "product": "Dated Brent (Platts) Financial Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/crude-oil/european-dated-brent-swap-futures_{}.html"
    },
    "DSF": {
        "symbol": "DSF",
        "product": "Dominion, South Point Natural Gas (Platts IFERC) Fixed Price Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/dominion-platts-iferc-fixed-price-swap_{}.html"
    },
    "TZI": {
        "symbol": "TZI",
        "product": "Transco Zone 6 Non-N.Y. Natural Gas (Platts Gas Daily/Platts IFERC) Index Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/transco-zone-6-non-ny-platts-gas-daily-platts-iferc-index-swap_{}.html"
    },
    "NDE": {
        "symbol": "NDE",
        "product": "UK Natural Gas Daily Future",
        "group": "products",
        "base_url": "http://www.cmegroup.com/trading/products/energy/natural-gas/uk-natural-gas-daily_{}.html"
    },
    "AFH": {
        "symbol": "AFH",
        "product": "WTS (Argus) vs. WTI Trade Month Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/crude-oil/wts-argus-vs-wti-trade-month-spread-swap-futures_{}.html"
    },
    "8XN": {
        "symbol": "8XN",
        "product": "OneOk, Oklahoma Natural Gas (Platts IFERC) Basis Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/oneok-oklahoma-natural-gas-basis-swap-futures-platts-iferc_{}.html"
    },
    "AKA": {
        "symbol": "AKA",
        "product": "NYISO Zone A Peak LBMP Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/nyiso-zone-a-peak-monthly-swap-futures_{}.html"
    },
    "DCB": {
        "symbol": "DCB",
        "product": "Dubai Crude Oil (Platts) Financial Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/crude-oil/dubai-crude-oil-calendar-swap-futures_{}.html"
    },
    "A47": {
        "symbol": "A47",
        "product": "PJM METED Zone Peak Calendar-Month Day-Ahead LMP Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/pjm-meted-zone-peak-calendar-month-day-ahead-lmp-swap-futures_{}.html"
    },
    "AJP": {
        "symbol": "AJP",
        "product": "PJM Off-Peak Calendar-Month LMP Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/pjm-off-peak-lmp-swap_{}.html"
    },
    "MNB": {
        "symbol": "MNB",
        "product": "Mont Belvieu Normal Butane LDH (OPIS) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/petrochemicals/mont-belvieu-normal-butane-ldh-opis-swap_{}.html"
    },
    "QG": {
        "symbol": "QG",
        "product": "E-mini Natural Gas Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/emini-natural-gas_{}.html"
    },
    "ARY": {
        "symbol": "ARY",
        "product": "RBOB Gasoline vs. NY Harbor ULSD Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/rbob-vs-heating-oil-swap-futures_{}.html"
    },
    "NRR": {
        "symbol": "NRR",
        "product": "NYISO Rest of the State Capacity Calendar-Month Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/nyiso-rest-of-the-state-capacity-calendar-month-swap-futures_{}.html"
    },
    "IT": {
        "symbol": "IT",
        "product": "Transco Zone 6 Natural Gas (Platts Gas Daily/Platts IFERC) Index Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/transco-zone-6-natural-gas-index-swap-futures-platts-gas-daily-platts-iferc_{}.html"
    },
    "GCI": {
        "symbol": "GCI",
        "product": "Gulf Coast HSFO (Platts) Brent Crack Spread Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/gulf-coast-no-6-fuel-oil-3pt0pct-platts-vs-brent-crack-spread-swap-futures_{}.html"
    },
    "NLS": {
        "symbol": "NLS",
        "product": "NY Harbor ULSD vs. Low Sulphur Gasoil (1,000bbl) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/ny-harbor-ulsd-vs-low-sulphur-gasoil-1000bbl_{}.html"
    },
    "AJS": {
        "symbol": "AJS",
        "product": "Los Angeles Jet (OPIS) vs. NY Harbor ULSD Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/los-angeles-jet-fuel-opis-spread-swap_{}.html"
    },
    "SZN": {
        "symbol": "SZN",
        "product": "Southern Natural, Louisiana Natural Gas (Platts IFERC) Basis Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/sonat-louisiana-natural-gas-basis-swap-futures-platts-iferc_{}.html"
    },
    "GLB": {
        "symbol": "GLB",
        "product": "1 Month Eurodollar Futures",
        "group": "interest-rates",
        "base_url": "http://www.cmegroup.com/trading/interest-rates/stir/1-month-libor_{}.html"
    },
    "VDL": {
        "symbol": "VDL",
        "product": "PJM AEP Dayton Hub Real-Time Peak Calendar-Day 5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/aep-dayton-hub-peak-daily-futures_{}.html"
    },
    "MGC": {
        "symbol": "MGC",
        "product": "E-micro Gold Futures",
        "group": "metals",
        "base_url": "http://www.cmegroup.com/trading/metals/precious/e-micro-gold_{}.html"
    },
    "ARE": {
        "symbol": "ARE",
        "product": "RBOB Gasoline Crack Spread Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/rbob-crack-spread-swap-futures_{}.html"
    },
    "RKA": {
        "symbol": "RKA",
        "product": "Singapore Jet Kerosene (Platts) vs. Gasoil (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/singapore-jet-regrade-jet-kero-vs-gasoil-swap-futures_{}.html"
    },
    "AJ2": {
        "symbol": "AJ2",
        "product": "PJM JCPL Zone Peak Calendar-Month Day-Ahead LMP Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/pjm-jcpl-zone-peak-calendar-month-day-ahead-lmp-swap-futures_{}.html"
    },
    "RT": {
        "symbol": "RT",
        "product": "RBOB Gasoline Bullet Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/rbob-gasoline-cash-settled_{}.html"
    },
    "MJP": {
        "symbol": "MJP",
        "product": "Aluminum Japan Premium (Platts) Futures",
        "group": "metals",
        "base_url": "http://www.cmegroup.com/trading/metals/base/aluminum-japan-premium-platts_{}.html"
    },
    "AZ1": {
        "symbol": "AZ1",
        "product": "Ethanol T2 FOB Rdam Including Duty (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/ethanol/ethanol-platts-t2-fob-rotterdam-including-duty-swap-futures_{}.html"
    },
    "XAE": {
        "symbol": "XAE",
        "product": "E-mini Energy Select Sector Futures",
        "group": "equity",
        "base_url": "http://www.cmegroup.com/trading/equity-index/select-sector-index/e-mini-energy-select-sector_{}.html"
    },
    "TXN": {
        "symbol": "TXN",
        "product": "TETCO STX Natural Gas (Platts IFERC) Basis Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/Tetco-stx-basis-swap-platts-IFERC-futures_{}.html"
    },
    "JET": {
        "symbol": "JET",
        "product": "NY Buckeye Jet Fuel (Platts) vs. NY Harbor ULSD Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/ny-buckeye-jet-fuel-platts-vs-ulsd_{}.html"
    },
    "CNH": {
        "symbol": "CNH",
        "product": "Standard-Size USD/Offshore RMB (CNH) Futures",
        "group": "fx",
        "base_url": "http://www.cmegroup.com/trading/fx/emerging-market/usd-cnh_{}.html"
    },
    "AY1": {
        "symbol": "AY1",
        "product": "PJM AECO Zone Peak Calendar-Month Day-Ahead LMP Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/pjm-aeco-zone-peak-calendar-month-day-ahead-lmp-swap-futures_{}.html"
    },
    "GBP": {
        "symbol": "GBP",
        "product": "British Pound / U.S. Dollar (GBP/USD) Physically Deliverable Future (CLS Eligible)",
        "group": "products",
        "base_url": "http://www.cmegroup.com/trading/products/fx/majors/gbp-usd_{}.html"
    },
    "AQ5": {
        "symbol": "AQ5",
        "product": "NYISO Zone C 5 MW Peak Calendar-Month Day-Ahead LBMP Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/nyiso-zone-c-5-mw-peak-calendar-month-day-ahead-swap-futures_{}.html"
    },
    "QXB": {
        "symbol": "QXB",
        "product": "CSX Coal (Platts OTC Broker Index) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/coal/eastern-rail-csx-coal-swap-futures_{}.html"
    },
    "N7": {
        "symbol": "N7",
        "product": "Algonquin City-Gates Natural Gas (Platts Gas Daily/Platts IFERC) Index Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/algonquin-city-gates-natural-gas-index-swap-futures-platts-gas-dailyplatts-iferc_{}.html"
    },
    "GNL": {
        "symbol": "GNL",
        "product": "NYISO Zone G Day-Ahead Peak Calendar-Day 5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/new-york-hub-nyiso-zone-g-peak-daily-lbmp-swap-futures_{}.html"
    },
    "PNL": {
        "symbol": "PNL",
        "product": "PJM Northern Illinois Hub Day-Ahead Peak Calendar-Day 5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/pjm-northern-illinois-hub-day-ahead-peak-calendar-day-25-mw_{}.html"
    },
    "NQN": {
        "symbol": "NQN",
        "product": "Tennessee Zone 0 Natural Gas (Platts IFERC) Basis Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/tennessee-zone-0-natural-gas-basis-swap-futures-platts-iferc_{}.html"
    },
    "AP1": {
        "symbol": "AP1",
        "product": "ERCOT North 345 kV Hub 5 MW Off-Peak Calendar-Day Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/ercot-north-zone-mcpe-5-mw-off-peak-calendar-day-swap-futures_{}.html"
    },
    "M6B": {
        "symbol": "M6B",
        "product": "E-micro British Pound/American Dollar Futures",
        "group": "fx",
        "base_url": "http://www.cmegroup.com/trading/fx/e-micros/e-micro-british-pound_{}.html"
    },
    "NHH": {
        "symbol": "NHH",
        "product": "NYISO NYC In-City Capacity Calendar-Month Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/nyiso-nyc-in-city-capacity-calendar-month-swap-futures_{}.html"
    },
    "PE": {
        "symbol": "PE",
        "product": "Demarc Natural Gas (Platts IFERC) Basis Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/northern-natural-gas-demarcation-basis-swap-futures_{}.html"
    },
    "ZJL": {
        "symbol": "ZJL",
        "product": "NYISO Zone J Day-Ahead Off-Peak Calendar-Day 5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/nyiso-zone-j-day-ahead-off-peak-calendar-day-25-mw_{}.html"
    },
    "COL": {
        "symbol": "COL",
        "product": "ISO New England Mass Hub Day-Ahead Peak Calendar-Day 5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/iso-new-england-hub-peak-daily-lmp-swap-futures_{}.html"
    },
    "AA8": {
        "symbol": "AA8",
        "product": "Group Three Sub-octane Gasoline (Platts) vs. RBOB Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/group-three-unleaded-gasoline-platts-vs-rbob-spread-swap_{}.html"
    },
    "AE3": {
        "symbol": "AE3",
        "product": "PJM BGE Zone Peak Calendar-Month Day-Ahead LMP Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/pjm-bge-zone-calendar-month-day-ahead-lmp-swap-futures_{}.html"
    },
    "A0F": {
        "symbol": "A0F",
        "product": "Mini Singapore Fuel Oil 180 cst (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/mini-singapore-fuel-oil-180-cst-platts-swap-futures_{}.html"
    },
    "A7E": {
        "symbol": "A7E",
        "product": "Argus Propane Far East Index Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/petrochemicals/argus-propane-far-east-index-swap-futures_{}.html"
    },
    "AL5": {
        "symbol": "AL5",
        "product": "PJM PPL Zone Peak Calendar-Month Day-Ahead LMP Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/pjm-ppl-zone-peak-calendar-month-day-ahead-lmp-swap-futures_{}.html"
    },
    "IV": {
        "symbol": "IV",
        "product": "Panhandle Natural Gas (Platts Gas Daily/Platts IFERC) Index Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/panhandle-natural-gas-index-swap-futures-platts-gas-daily-platts-iferc_{}.html"
    },
    "QO": {
        "symbol": "QO",
        "product": "E-mini Gold Futures",
        "group": "metals",
        "base_url": "http://www.cmegroup.com/trading/metals/precious/e-mini-gold_{}.html"
    },
    "M6A": {
        "symbol": "M6A",
        "product": "E-micro Australian Dollar/American Dollar Futures",
        "group": "fx",
        "base_url": "http://www.cmegroup.com/trading/fx/e-micros/e-micro-australian-dollar_{}.html"
    },
    "NME": {
        "symbol": "NME",
        "product": "UK Natural Gas Calendar Month Future",
        "group": "products",
        "base_url": "http://www.cmegroup.com/trading/products/energy/natural-gas/uk-natural-gas-calendar-month_{}.html"
    },
    "SD": {
        "symbol": "SD",
        "product": "Singapore Fuel Oil 180 cst (Platts) vs. 380 cst (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/singapore-180cst-fuel-oil-vs-380cst-fuel-oil-spread-swap-futures_{}.html"
    },
    "A55": {
        "symbol": "A55",
        "product": "NYISO Zone E 5 MW Peak Calendar-Month Day-Ahead LBMP Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/nyiso-zone-e-5-mw-peak-calendar-month-day-ahead-lbmp-swap-futures_{}.html"
    },
    "PGG": {
        "symbol": "PGG",
        "product": "PGP Polymer Grade Propylene (PCW) Financial Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/petrochemicals/polymer-grade-propylene-pcw-calendar-swap_{}.html"
    },
    "JNL": {
        "symbol": "JNL",
        "product": "NYISO Zone J Day-Ahead Peak Calendar-Day 5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/new-york-hub-nyiso-zone-j-peak-daily-swap-futures_{}.html"
    },
    "JA": {
        "symbol": "JA",
        "product": "Japan C&F Naphtha (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/japan-cf-naphtha-platts-swap_{}.html"
    },
    "UA": {
        "symbol": "UA",
        "product": "Singapore Fuel Oil 180 cst (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/singapore-fuel-oil-180cst-calendar-swap-futures_{}.html"
    },
    "J7": {
        "symbol": "J7",
        "product": "E-mini Japanese Yen Futures",
        "group": "fx",
        "base_url": "http://www.cmegroup.com/trading/fx/g10/e-mini-japanese-yen_{}.html"
    },
    "UDL": {
        "symbol": "UDL",
        "product": "PJM Northern Illinois Hub Real-Time Peak Calendar-Day 5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/northern-illinois-hub-peak-daily-swap-futures_{}.html"
    },
    "L2": {
        "symbol": "L2",
        "product": "Columbia Gulf, Mainline Natural Gas (Platts Gas Daily/Platts IFERC) Index Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/columbia-gulf-mainline-natural-gas-index-swap-futures-platts-gas-daily-platts-iferc_{}.html"
    },
    "A8I": {
        "symbol": "A8I",
        "product": "Mont Belvieu Iso-Butane (OPIS) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/petrochemicals/mont-belvieu-iso-butane-5-decimal-opis-swap-futures_{}.html"
    },
    "Q1": {
        "symbol": "Q1",
        "product": "Columbia Gas TCO (Platts Gas Daily/Platts IFERC) Index Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/tco-natural-gas-index-swap-futures_{}.html"
    },
    "PLN": {
        "symbol": "PLN",
        "product": "Polish Zloty Futures",
        "group": "fx",
        "base_url": "http://www.cmegroup.com/trading/fx/emerging-market/polish-zloty_{}.html"
    },
    "XW": {
        "symbol": "XW",
        "product": "Mini-sized Chicago SRW Wheat Futures",
        "group": "agricultural",
        "base_url": "http://www.cmegroup.com/trading/agricultural/grain-and-oilseed/mini-sized-wheat_{}.html"
    },
    "FME": {
        "symbol": "FME",
        "product": "Urea (Granular) FOB Middle East Future",
        "group": "products",
        "base_url": "http://www.cmegroup.com/trading/products/agricultural/fertilizer/urea-granular-fob-middle-east_{}.html"
    },
    "EXR": {
        "symbol": "EXR",
        "product": "RBOB Gasoline vs. Euro-bob Oxy NWE Barges (Argus) (350,000 gallons) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/rbob-gasoline-vs-euro-bob-oxy-argus-nwe-barges-1000mt-swap-futures_{}.html"
    },
    "MJY": {
        "symbol": "MJY",
        "product": "E-micro Japanese Yen/American Dollar Futures",
        "group": "fx",
        "base_url": "http://www.cmegroup.com/trading/fx/e-micros/e-micro-japanese-yen-us-dollar_{}.html"
    },
    "APS": {
        "symbol": "APS",
        "product": "European Propane CIF ARA (Argus) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/petrochemicals/european-propane-cif-ara-argus-swap_{}.html"
    },
    "AJY": {
        "symbol": "AJY",
        "product": "Australian Dollar/Japanese Yen Futures",
        "group": "fx",
        "base_url": "http://www.cmegroup.com/trading/fx/g10/australian-dollar-japanese-yen_{}.html"
    },
    "VML": {
        "symbol": "VML",
        "product": "PJM AEP Dayton Hub Real-Time Peak Calendar-Month 2.5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/aep-dayton-hub-peak-monthly-futures_{}.html"
    },
    "UN": {
        "symbol": "UN",
        "product": "European Naphtha Cargoes CIF NWE (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/european-naphtha-calendar-swap_{}.html"
    },
    "NM": {
        "symbol": "NM",
        "product": "Tennessee 500 Leg Natural Gas (Platts IFERC) Basis Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/tennessee-500-leg-natural-gas-basis-swap-futures-platts-iferc_{}.html"
    },
    "MPP": {
        "symbol": "MPP",
        "product": "PJM ATSI Zone 5 MW Peak Calendar-Month Day-Ahead Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/pjm-atsi-zone-5-mw-peak-calendar-month-day-ahead-swap-futures_{}.html"
    },
    "DVS": {
        "symbol": "DVS",
        "product": "Sumas Natural Gas (Platts IFERC) Fixed Price Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/sumas-natural-gas-fixed-price-futures_{}.html"
    },
    "XAB": {
        "symbol": "XAB",
        "product": "E-mini Materials Select Sector Futures",
        "group": "equity",
        "base_url": "http://www.cmegroup.com/trading/equity-index/select-sector-index/e-mini-materials-select-sector_{}.html"
    },
    "MJN": {
        "symbol": "MJN",
        "product": "Mini Japan C&F Naphtha (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/mini-japan-candf-naphtha-platts-swap_{}.html"
    },
    "FPN": {
        "symbol": "FPN",
        "product": "Florida Gas, Zone 3 Natural Gas (Platts IFERC) Basis Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/florida-gas-zone-3-natural-gas-basis-swap-futures_{}.html"
    },
    "AGE": {
        "symbol": "AGE",
        "product": "Gulf Coast Jet Fuel (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/gulf-coast-jet-fuel-platts-calendar-swap_{}.html"
    },
    "FSS": {
        "symbol": "FSS",
        "product": "1% Fuel Oil Cargoes FOB NWE (Platts) vs. 3.5% Fuel Oil Barges FOB Rdam (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/fuel-oil-diff-1pct-nwe-cargoes-vs-35pct-barges-swap_{}.html"
    },
    "PIO": {
        "symbol": "PIO",
        "product": "Iron Ore 62% Fe, CFR North China (Platts) Futures  ",
        "group": "metals",
        "base_url": "http://www.cmegroup.com/trading/metals/ferrous/iron-ore-62pct-fe-cfr-north-china-platts-swap-futures_{}.html"
    },
    "AKS": {
        "symbol": "AKS",
        "product": "Singapore Jet Kerosene (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/singapore-jet-kerosene-swap-futures_{}.html"
    },
    "EDP": {
        "symbol": "EDP",
        "product": "Aluminium European Premium Duty-Paid (Metal Bulletin) Futures",
        "group": "metals",
        "base_url": "http://www.cmegroup.com/trading/metals/base/aluminium-european-premium-duty-paid-metal-bulletin_{}.html"
    },
    "ADB": {
        "symbol": "ADB",
        "product": "Brent Crude Oil vs. Dubai Crude Oil (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/crude-oil/brent-dubai-swap-futures_{}.html"
    },
    "AVP": {
        "symbol": "AVP",
        "product": "PJM AEP Dayton Hub Off-Peak LMP Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/aep-dayton-hub-off-peak-monthly-swap-futures_{}.html"
    },
    "ANL": {
        "symbol": "ANL",
        "product": "NYISO Zone A Day-Ahead Peak Calendar-Day 5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/new-york-hub-nyiso-zone-a-peak-daily-lbmp-swap-futures_{}.html"
    },
    "A7Y": {
        "symbol": "A7Y",
        "product": "NY ULSD (Argus) vs. NY Harbor ULSD Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/new-york-ulsd-vs-heating-oil-spread-swap-futures_{}.html"
    },
    "SEK": {
        "symbol": "SEK",
        "product": "Swedish Krona Futures",
        "group": "fx",
        "base_url": "http://www.cmegroup.com/trading/fx/g10/swedish-krona_{}.html"
    },
    "A5C": {
        "symbol": "A5C",
        "product": "Chicago ULSD (Platts) vs. NY Harbor ULSD Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/chicago-ultra-low-sulfur-diesel-ulsd-platts-vs-heating-oil-spread-swap_{}.html"
    },
    "FLP": {
        "symbol": "FLP",
        "product": "Freight Route Liquid Petroleum Gas (Baltic) Future",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/freight/freight-route-lpg-baltic-futures_{}.html"
    },
    "ALW": {
        "symbol": "ALW",
        "product": "Australian Coking Coal (Platts) Low Vol Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/coal/australian-coking-coal-platts-low-vol-swap_{}.html"
    },
    "MXB": {
        "symbol": "MXB",
        "product": "Mini RBOB Gasoline vs. Gasoline Euro-bob Oxy NWE Barges (Argus) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/mini-rbob-gasoline-vs-euro-bob-oxy-nwe-barges-futures_{}.html"
    },
    "MCD": {
        "symbol": "MCD",
        "product": "E-micro Canadian Dollar/American Dollar Futures",
        "group": "fx",
        "base_url": "http://www.cmegroup.com/trading/fx/e-micros/e-micro-canadian-dollar-us-dollar_{}.html"
    },
    "B1U": {
        "symbol": "B1U",
        "product": "30-Year USD Deliverable Interest Rate Swap Futures",
        "group": "interest-rates",
        "base_url": "http://www.cmegroup.com/trading/interest-rates/deliverable-swaps/30-year-deliverable-interest-rate-swap-futures_{}.html"
    },
    "SIR": {
        "symbol": "SIR",
        "product": "Indian Rupee/USD Futures",
        "group": "fx",
        "base_url": "http://www.cmegroup.com/trading/fx/emerging-market/indian-rupee_{}.html"
    },
    "AKL": {
        "symbol": "AKL",
        "product": "Los Angeles CARB Diesel (OPIS) vs. NY Harbor ULSD Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/los-angeles-carbob-diesel-opis-spread-swap_{}.html"
    },
    "AKB": {
        "symbol": "AKB",
        "product": "NYISO Zone A Off-Peak LBMP Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/nyiso-zone-a-off-peak-monthly-futures_{}.html"
    },
    "RSV": {
        "symbol": "RSV",
        "product": "E-mini Russell 1000 Value Index Futures",
        "group": "equity",
        "base_url": "http://www.cmegroup.com/trading/equity-index/us-index/e-mini-russell-1000-value-index_{}.html"
    },
    "A9N": {
        "symbol": "A9N",
        "product": "Argus Propane (Saudi Aramco) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/petrochemicals/argus-propane-saudi-aramco-swap-futures_{}.html"
    },
    "AP2": {
        "symbol": "AP2",
        "product": "ISO New England Connecticut Zone 5 MW Peak Calendar-Month Day-Ahead LMP Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/nepool-connecticut-5-mw-peak-calendar-month-day-ahead-lmp-swap-futures_{}.html"
    },
    "ECD": {
        "symbol": "ECD",
        "product": "Euro/Canadian Dollar Futures",
        "group": "fx",
        "base_url": "http://www.cmegroup.com/trading/fx/g10/euro-fx-canadian-dollar_{}.html"
    },
    "AUI": {
        "symbol": "AUI",
        "product": "European 3.5% Fuel Oil Cargoes FOB MED (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/european-35pct-fuel-oil-mediterranean-med-calendar-swap_{}.html"
    },
    "SIL": {
        "symbol": "SIL",
        "product": "1,000-oz. Silver Futures",
        "group": "metals",
        "base_url": "http://www.cmegroup.com/trading/metals/precious/1000-oz-silver_{}.html"
    },
    "NOK": {
        "symbol": "NOK",
        "product": "Norwegian Krone Futures",
        "group": "fx",
        "base_url": "http://www.cmegroup.com/trading/fx/g10/norwegian-krone_{}.html"
    },
    "SDI": {
        "symbol": "SDI",
        "product": "S&P 500 Quarterly Dividend Index Futures",
        "group": "equity",
        "base_url": "http://www.cmegroup.com/trading/equity-index/us-index/sp-500-quarterly-dividend-index_{}.html"
    },
    "6ZN": {
        "symbol": "6ZN",
        "product": "Tennessee 800 Leg Natural Gas (Platts IFERC) Basis Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/tennessee-800-leg-natural-gas-basis_{}.html"
    },
    "A1D": {
        "symbol": "A1D",
        "product": "RBOB Gasoline BALMO Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/rbob-gasoline-balmo-calendar-swap_{}.html"
    },
    "AKP": {
        "symbol": "AKP",
        "product": "NYISO Zone J Off-Peak LBMP Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/nyiso-zone-j-off-peak-monthly-swap-futures_{}.html"
    },
    "A8L": {
        "symbol": "A8L",
        "product": "Conway Natural Gasoline (OPIS) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/petrochemicals/conway-natural-gasoline-opis-swap_{}.html"
    },
    "7D": {
        "symbol": "7D",
        "product": "3.5% Fuel Oil CIF MED (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/35-fuel-oil-cif-med-swap-futures_{}.html"
    },
    "AEZ": {
        "symbol": "AEZ",
        "product": "NY Ethanol (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/ethanol/new-york-ethanol-platts-swap_{}.html"
    },
    "AI5": {
        "symbol": "AI5",
        "product": "ERCOT North 345 kV Hub 5 MW Peak Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/ercot-north-zone-mcpe-5-mw-peak-swap-futures_{}.html"
    },
    "NOO": {
        "symbol": "NOO",
        "product": "Naphtha Cargoes CIF NWE (Platts) Crack Spread (1000mt) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/naphtha-platts-cargoes-cif-nwe-crack-spread-1000mt-swap-futures_{}.html"
    },
    "A4L": {
        "symbol": "A4L",
        "product": "NYISO Zone F 5 MW Peak Calendar-Month Day-Ahead LBMP Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/nyiso-zone-f-5-mw-peak-calendar-month-day-ahead-lbmp-swap-futures_{}.html"
    },
    "A49": {
        "symbol": "A49",
        "product": "PJM PENELEC Zone Peak Calendar-Month Day-Ahead LMP Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/pjm-penelec-zone-peak-calendar-month-day-ahead-lmp-swap-futures_{}.html"
    },
    "IR": {
        "symbol": "IR",
        "product": "Rockies Natural Gas (Platts Gas Daily/Platts IFERC) Index Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/rockies-kern-opal-nw-natural-gas-index-swap-futures-platts-gas-daily-platts-iferc_{}.html"
    },
    "PDL": {
        "symbol": "PDL",
        "product": "MISO Indiana Hub Day-Ahead Peak Calendar-Day 5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/midwest-iso-indiana-hub-5-mw-peak-calendar-day-day-ahead-swap-futures_{}.html"
    },
    "PAL": {
        "symbol": "PAL",
        "product": "PJM AEP Dayton Hub Day-Ahead Peak Calendar-Day 5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/pjm-aep-dayton-hub-day-ahead-peak-calendar-day-25-mw_{}.html"
    },
    "XR": {
        "symbol": "XR",
        "product": "Rockies Natural Gas (Platts IFERC) Fixed Price Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/rockies-natural-gas-fixed-price-swap_{}.html"
    },
    "AQA": {
        "symbol": "AQA",
        "product": "Low Sulphur Gasoil Mini Financial Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/gasoil-ice-mini-calendar-swap_{}.html"
    },
    "8ZN": {
        "symbol": "8ZN",
        "product": "Southern Star, Tx.-Okla.-Kan. Natural Gas (Platts IFERC) Basis Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/southern-star-texas-oklahoma-kansas-natural-gas-basis-swap-futures-platts-iferc_{}.html"
    },
    "DI": {
        "symbol": "DI",
        "product": "Demarc Natural Gas (Platts Gas Daily/Platts IFERC) Index Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/demarc-natural-gas-index-swap-futures-platts-gas-daily-platts-iferc_{}.html"
    },
    "IL": {
        "symbol": "IL",
        "product": "Permian Natural Gas (Platts Gas Daily/Platts IFERC) Index Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/el-paso-permian-natural-gas-index-swap-futures-platts-gas-daily-platts-iferc_{}.html"
    },
    "CFS": {
        "symbol": "CFS",
        "product": "Columbia Gas TCO (Platts IFERC) Fixed Price Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/columbia-gas-tco-platts-iferc-fixed-price-swap_{}.html"
    },
    "MFS": {
        "symbol": "MFS",
        "product": "MichCon Natural Gas (Platts IFERC) Fixed Price Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/mich-con-natural-gas-fixed-price-swap_{}.html"
    },
    "EWG": {
        "symbol": "EWG",
        "product": "East-West Gasoline Spread (Platts-Argus) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/east-west-gasoline-spread-platts-argus-swap-futures_{}.html"
    },
    "EAD": {
        "symbol": "EAD",
        "product": "Euro/Australian Dollar Futures",
        "group": "fx",
        "base_url": "http://www.cmegroup.com/trading/fx/g10/euro-fx-australian-dollar_{}.html"
    },
    "AUO": {
        "symbol": "AUO",
        "product": "PJM Northern Illinois Hub Off-Peak LMP Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/northern-illinois-off-peak-monthly-swap-futures_{}.html"
    },
    "ATP": {
        "symbol": "ATP",
        "product": "ULSD 10ppm Cargoes CIF NWE (Platts) vs. Low Sulphur Gasoil Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/gasoil-10ppm-cargoes-cif-nwe-vs-ice-gasoil-swap_{}.html"
    },
    "AET": {
        "symbol": "AET",
        "product": "European Diesel 10 ppm Barges FOB Rdam (Platts) vs. Low Sulphur Gasoil Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/european-gasoil-10ppm-rotterdam-barges-vs-gasoil_{}.html"
    },
    "AFK": {
        "symbol": "AFK",
        "product": "3.5% Fuel Oil Cargoes FOB MED (Platts) vs. 3.5% Fuel Oil Barges FOB Rdam (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/35pct-fuel-oil-rotterdam-vs-35pct-fob-med-spread-swap_{}.html"
    },
    "MGN": {
        "symbol": "MGN",
        "product": "Mini ULSD 10ppm Cargoes CIF NWE (Platts) vs. Low Sulphur Gasoil Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/mini-gasoil-10ppm-platts-cargoes-cif-nwe-vs-gasoil-swap-futures_{}.html"
    },
    "AP7": {
        "symbol": "AP7",
        "product": "ISO New England North East Massachusetts Zone 5 MW Peak Calendar-Month Day-Ahead LMP Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/nepool-ne-mass-5-peak-mw-day-ahead-calendar-month-day-ahead-swap-futures_{}.html"
    },
    "AH1": {
        "symbol": "AH1",
        "product": "NY 3.0% Fuel Oil (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/new-york-30pct-fuel-oil-platts-swap_{}.html"
    },
    "Z1A": {
        "symbol": "Z1A",
        "product": "European Ethanol T2 fob Rotterdam Inc Duty (Platts) Calendar Month Future",
        "group": "products",
        "base_url": "http://www.cmegroup.com/trading/products/energy/biofuels/european-ethanol-t2-fob-rotterdam-inc-duty-platts-calendar-future_{}.html"
    },
    "EPN": {
        "symbol": "EPN",
        "product": "European Propane CIF ARA (Argus) vs. Naphtha Cargoes CIF NWE (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/european-propane-cif-ara-argus-vs-naphtha-cif-nwe-platts-swap_{}.html"
    },
    "AEJ": {
        "symbol": "AEJ",
        "product": "MISO Indiana Hub (formerly Cinergy Hub) Off-Peak LMP Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/cinergy-hub-off-peak-calendar-month-lmp-swap-futures_{}.html"
    },
    "A7I": {
        "symbol": "A7I",
        "product": "Gasoline Euro-bob Oxy NWE Barges (Argus) Crack Spread BALMO Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/gasoline-euro-bob-oxy-new-barges-crack-spread-balmo-swap-futures_{}.html"
    },
    "PX": {
        "symbol": "PX",
        "product": "NGPL Mid-Con Natural Gas (Platts Gas Daily) Swing Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/ngpl-midcontinent-natural-gas-swing-swap-futures_{}.html"
    },
    "AJL": {
        "symbol": "AJL",
        "product": "Los Angeles CARBOB Gasoline (OPIS) vs. RBOB Gasoline Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/los-angeles-carbob-gasoline-opis-spread-swap_{}.html"
    },
    "DRS": {
        "symbol": "DRS",
        "product": "Bloomberg Roll Select Commodity Index Futures",
        "group": "agricultural",
        "base_url": "http://www.cmegroup.com/trading/agricultural/commodity-index/bloomberg-roll-select-commodity-index_{}.html"
    },
    "A8O": {
        "symbol": "A8O",
        "product": "Mont Belvieu LDH Propane (OPIS) BALMO Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/petrochemicals/mont-belvieu-ldh-propane-opis-balmo-swap-futures_{}.html"
    },
    "AVU": {
        "symbol": "AVU",
        "product": "Singapore Gasoil (Platts) BALMO Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/singapore-gasoil-balmo-swap-futures_{}.html"
    },
    "PJY": {
        "symbol": "PJY",
        "product": "British Pound/Japanese Yen Futures",
        "group": "fx",
        "base_url": "http://www.cmegroup.com/trading/fx/g10/british-pound-japanese-yen_{}.html"
    },
    "NIL": {
        "symbol": "NIL",
        "product": "ISO New England Mass Hub Day-Ahead Peak Calendar-Month 2.5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/iso-new-england-internal-hub-peak-location-marginal-pricing-lmp-swap-futures_{}.html"
    },
    "HJC": {
        "symbol": "HJC",
        "product": "Jet Cargoes CIF NWE (Platts) vs. Low Sulphur Gasoil Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/european-jet-fuel-platts-cif-nwe-vs-gasoil-swap_{}.html"
    },
    "A8J": {
        "symbol": "A8J",
        "product": "Mont Belvieu Normal Butane (OPIS) BALMO Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/petrochemicals/mont-belvieu-normal-butane-opis-balmo-swap_{}.html"
    },
    "MEE": {
        "symbol": "MEE",
        "product": "Mini European Naphtha (Platts) BALMO Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/mini-european-naphtha-platts-balmo-swap-futures_{}.html"
    },
    "AS4": {
        "symbol": "AS4",
        "product": "PJM APS Zone Peak Calendar-Month Day-Ahead LMP Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/pjm-aps-zone-peak-calendar-month-day-ahead-lmp-swap-futures_{}.html"
    },
    "OPO": {
        "symbol": "OPO",
        "product": "Ontario Peak Calendar-Day Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/ontario-peak-calendar-day-swap-futures_{}.html"
    },
    "MJC": {
        "symbol": "MJC",
        "product": "Mini European Jet Kero Cargoes CIF NWE (Platts) vs. Low Sulphur Gasoil Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/mini-european-jet-kero-platts-cargoes-cif-nwe-vs-gasoil-swap-futures_{}.html"
    },
    "AJB": {
        "symbol": "AJB",
        "product": "Japan C&F Naphtha (Platts) Brent Crack Spread Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/japan-cf-naphtha-crack-spread-swap_{}.html"
    },
    "AKI": {
        "symbol": "AKI",
        "product": "ISO New England Monthly Off Peak LMP Swap Future",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/iso-new-england-off-peak-lmp-monthly-swap-futures_{}.html"
    },
    "MQ": {
        "symbol": "MQ",
        "product": "Los Angeles Jet Fuel (Platts) vs. NY Harbor ULSD Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/la-jet-fuel-vs-no-2-heating-oil-platts-spread-swap_{}.html"
    },
    "EWN": {
        "symbol": "EWN",
        "product": "East-West Naphtha: Japan C&F vs. Cargoes CIF NWE Spread (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/east-west-naphtha-japan-cf-vs-cargoes-cif-nwe-spread-platts-swap-futures_{}.html"
    },
    "A1M": {
        "symbol": "A1M",
        "product": "Gulf Coast Jet (Platts) Up-Down BALMO Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/jet-fuel-up-down-balmo-calendar-swap_{}.html"
    },
    "BUS": {
        "symbol": "BUS",
        "product": "U.S. Midwest Busheling Ferrous Scrap (AMM) Futures",
        "group": "metals",
        "base_url": "http://www.cmegroup.com/trading/metals/ferrous/us-midwest-busheling-ferrous-scrap_{}.html"
    },
    "MEL": {
        "symbol": "MEL",
        "product": "MISO Indiana Hub (formerly Cinergy Hub) Real-Time Peak Calendar-Month 2.5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/cinergy-hub-peak-calendar-month-lmp-swap-futures_{}.html"
    },
    "A91": {
        "symbol": "A91",
        "product": "Argus Propane Far East Index vs. European Propane CIF ARA (Argus) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/petrochemicals/argus-propane-far-east-index-vs-european-propane-cif-ara-argus-swap-futures_{}.html"
    },
    "NDN": {
        "symbol": "NDN",
        "product": "ANR, Louisiana Natural Gas (Platts IFERC) Basis Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/anr-louisiana-natural-gas-basis-swap-futures-platts-iferc_{}.html"
    },
    "0E": {
        "symbol": "0E",
        "product": "Mini European 3.5% Fuel Oil Barges FOB Rdam (Platts) BALMO Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/mini-european-35pct-fuel-oil-platts-barges-fob-rdam-balmo-swap-futures_{}.html"
    },
    "RMB": {
        "symbol": "RMB",
        "product": "Chinese Renminbi/USD Futures",
        "group": "fx",
        "base_url": "http://www.cmegroup.com/trading/fx/emerging-market/chinese-renminbi_{}.html"
    },
    "UML": {
        "symbol": "UML",
        "product": "PJM Northern Illinois Hub Real-Time Peak Calendar-Month 2.5 MW Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/northern-illinois-hub-peak-monthly-swap-futures_{}.html"
    },
    "AUF": {
        "symbol": "AUF",
        "product": "European 1% Fuel Oil Cargoes FOB NWE (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/european-1pct-fuel-oil-northwest-europe-nwe-calendar-swap-futures-platts_{}.html"
    },
    "GPB": {
        "symbol": "GPB",
        "product": "German Power Baseload Calendar Month Future",
        "group": "products",
        "base_url": "http://www.cmegroup.com/trading/products/energy/electricity/german-power-baseload-calendar-month_{}.html"
    },
    "A8M": {
        "symbol": "A8M",
        "product": "Conway Normal Butane (OPIS) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/petrochemicals/conway-normal-butane-opis-swap_{}.html"
    },
    "BR7": {
        "symbol": "BR7",
        "product": "Gasoline Euro-bob Oxy NWE Barges (Argus) BALMO Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/gasoline-euro-bob-oxy-new-barges-balmo-swap-futures_{}.html"
    },
    "CCP": {
        "symbol": "CCP",
        "product": "Cocoa Future",
        "group": "products",
        "base_url": "http://www.cmegroup.com/trading/products/agricultural/softs/physically-delivered-cocoa_{}.html"
    },
    "FEW": {
        "symbol": "FEW",
        "product": "East-West Fuel Oil Spread (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/eastwest-arb-singapore-180cst-vs-rotterdam-35pct-fuel-oil-spread-swap_{}.html"
    },
    "AT0": {
        "symbol": "AT0",
        "product": "Mini European 1% Fuel Oil Barges FOB Rdam (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/mini-european-1pct-fuel-oil-platts-barges-fob-rdam-swap-futures_{}.html"
    },
    "IBV": {
        "symbol": "IBV",
        "product": "USD-Denominated Ibovespa Index Futures",
        "group": "equity",
        "base_url": "http://www.cmegroup.com/trading/equity-index/international-index/usd-denominated-ibovespa_{}.html"
    },
    "NYH": {
        "symbol": "NYH",
        "product": "NY 0.3% Fuel Oil HiPr (Platts) vs. NY Fuel Oil 1.0% (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/new-york-0point3pct-fuel-oil-hipr-vs-new-york-fuel-oil-1pct-platts-swap-futures_{}.html"
    },
    "AKG": {
        "symbol": "AKG",
        "product": "NYISO Zone G Peak LBMP Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/nyiso-zone-g-peak-monthly-swap-futures_{}.html"
    },
    "AUY": {
        "symbol": "AUY",
        "product": "NY ULSD (Platts) vs. NY Harbor ULSD Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/new-york-ultra-low-sulfur-diesel-ulsd-platts-vs-nymex-heating-oil-ho-spread-swap_{}.html"
    },
    "5L": {
        "symbol": "5L",
        "product": "Mini Singapore Fuel Oil 180 cst (Platts) BALMO Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/mini-singapore-fuel-oil-180-cst-platts-balmo-swap-futures_{}.html"
    },
    "AUD": {
        "symbol": "AUD",
        "product": "Australian Dollar / U.S. Dollar (AUD/USD) Physically Deliverable Future (CLS Eligible)",
        "group": "products",
        "base_url": "http://www.cmegroup.com/trading/products/fx/majors/aud-usd_{}.html"
    },
    "NYF": {
        "symbol": "NYF",
        "product": "NY Fuel Oil 1.0% (Platts) vs. European 1% Fuel Oil Cargoes FOB NWE (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/new-york-fuel-oil-1pct-vs-european-1pct-fuel-oil-cargoes-fob-nwe-platts-swap-futures_{}.html"
    },
    "ESK": {
        "symbol": "ESK",
        "product": "Euro/Swedish Krona Futures",
        "group": "fx",
        "base_url": "http://www.cmegroup.com/trading/fx/g10/euro-fx-swedish-krona_{}.html"
    },
    "L4": {
        "symbol": "L4",
        "product": "Tennessee 800 Leg Natural Gas (Platts Gas Daily/Platts IFERC) Index Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/tennessee-800-leg-natural-gas-index-swap-futures-platts-gas-daily-platts-iferc_{}.html"
    },
    "ENS": {
        "symbol": "ENS",
        "product": "European 1% Fuel Oil Cargoes FOB MED vs. European 1% Fuel Oil Cargoes FOB NWE Spread (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/european-1pct-fuel-oil-cargoes-fob-med-vs-european-1pct-fuel-oil-cargoes-fob-nwe-spread-platts-swap-futures_{}.html"
    },
    "JE": {
        "symbol": "JE",
        "product": "EIA Flat Tax U.S. Retail Gasoline Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/eia-flat-tax-us-retail-gasoline-swap-futures_{}.html"
    },
    "MEB": {
        "symbol": "MEB",
        "product": "Mini Gasoline Euro-bob Oxy NWE Barges (Argus) BALMO Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/mini-gasoline-euro-bob-oxy-nwe-barges-balmo-futures_{}.html"
    },
    "GCC": {
        "symbol": "GCC",
        "product": "Gulf Coast Unl 87 Gasoline M2 (Platts) Crack Spread Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/gulf-coast-unl-87-gasoline-m2-platts-crack-spread-swap_{}.html"
    },
    "MSF": {
        "symbol": "MSF",
        "product": "E-micro Swiss Franc/American Dollar Futures",
        "group": "fx",
        "base_url": "http://www.cmegroup.com/trading/fx/e-micros/e-micro-swiss-franc-us-dollar_{}.html"
    },
    "AY3": {
        "symbol": "AY3",
        "product": "NY 2.2% Fuel Oil (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/new-york-22pct-fuel-oil-platts-swap_{}.html"
    },
    "B2": {
        "symbol": "B2",
        "product": "Transco Zone 4 Natural Gas (Platts Gas Daily/Platts IFERC) Index Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/transco-zone-4-natural-gas-index-swap-futures-platts-gas-daily-platts-iferc_{}.html"
    },
    "MXR": {
        "symbol": "MXR",
        "product": "Mini RBOB Gasoline vs. Gasoline Euro-bob Oxy NWE Barges (Argus) BALMO Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/mini-rbob-gasoline-vs-euro-bob-oxy-nwe-barges-balmo-futures_{}.html"
    },
    "MMF": {
        "symbol": "MMF",
        "product": "Mini 3.5% Fuel Oil Cargoes FOB MED (Platts) Financial Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/mini-35pct-fuel-oil-platts-cargoes-fob-med-calendar-swap_{}.html"
    },
    "A3G": {
        "symbol": "A3G",
        "product": "Premium Unleaded Gasoline 10 ppm FOB MED (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/premium-unleaded-10-ppm-platts-fob-med-swap_{}.html"
    },
    "0B": {
        "symbol": "0B",
        "product": "Mini European 1% Fuel Oil Cargoes FOB NWE (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/mini-european-1pct-fuel-oil-platts-cargoes-fob-nwe-swap-futures_{}.html"
    },
    "A42": {
        "symbol": "A42",
        "product": "WTI BALMO Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/crude-oil/wti-balmo-swap-futures_{}.html"
    },
    "FZE": {
        "symbol": "FZE",
        "product": "Ethanol Forward Month Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/ethanol/cbot-ethanol-forward-month-swap_{}.html"
    },
    "STT": {
        "symbol": "STT",
        "product": "Singapore Gasoil 10 ppm (Platts) vs. Singapore Gasoil (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/singapore-gasoil-10-ppm-vs-0point5pct-sulfur-spread-platts-swap-futures_{}.html"
    },
    "AV0": {
        "symbol": "AV0",
        "product": "Singapore Mogas 95 Unleaded (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/singapore-mogas-95-unleaded-platts-swap-futures_{}.html"
    },
    "CRB": {
        "symbol": "CRB",
        "product": "Gulf Coast CBOB Gasoline A2 (Platts) vs. RBOB Gasoline Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/gulf-coast-cbob-gasoline-a2-platts-vs-rbob-spread-swap_{}.html"
    },
    "AKH": {
        "symbol": "AKH",
        "product": "NYISO Zone G Off-Peak LBMP Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/nyiso-zone-g-off-peak-monthly-swap-futures_{}.html"
    },
    "AVZ": {
        "symbol": "AVZ",
        "product": "Gulf Coast HSFO (Platts) BALMO Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/gulf-coast-3pct-fuel-oil-balmo-swap_{}.html"
    },
    "ALI": {
        "symbol": "ALI",
        "product": "Aluminum Futures",
        "group": "metals",
        "base_url": "http://www.cmegroup.com/trading/metals/base/aluminum_{}.html"
    },
    "MUD": {
        "symbol": "MUD",
        "product": "Mini European Diesel 10 ppm Barges FOB Rdam (Platts) vs. Low Sulphur Gasoil Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/mini-european-diesel-10ppm-platts-barges-fob-rdam-vs-ice-gasoil-swap_{}.html"
    },
    "AKR": {
        "symbol": "AKR",
        "product": "European 3.5% Fuel Oil Barges FOB Rdam (Platts) BALMO Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/european-35pct-fuel-oil-rotterdam-balmo-calendar-swap_{}.html"
    },
    "AI7": {
        "symbol": "AI7",
        "product": "ERCOT North 345 kV Hub 5 MW Peak Calendar-Day Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/ercot-north-zone-mcpe-5-mw-peak-calendar-day-swap-futures_{}.html"
    },
    "QI": {
        "symbol": "QI",
        "product": "E-mini Silver Futures",
        "group": "metals",
        "base_url": "http://www.cmegroup.com/trading/metals/precious/e-mini-silver_{}.html"
    },
    "WFS": {
        "symbol": "WFS",
        "product": "Waha Natural Gas (Platts IFERC) Fixed Price Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/waha-natural-gas-fixed-price-swap_{}.html"
    },
    "MBL": {
        "symbol": "MBL",
        "product": "Mont Belvieu LDH Iso-Butane (OPIS) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/petrochemicals/mont-belvieu-ldh-iso-butane-opis-swap-futures_{}.html"
    },
    "MFD": {
        "symbol": "MFD",
        "product": "Mini 1% Fuel Oil Cargoes FOB MED (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/mini-1pct-fuel-oil-cargoes-fob-med-platts-swaps_{}.html"
    },
    "AGX": {
        "symbol": "AGX",
        "product": "European Low Sulphur Gasoil Financial Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/european-gasoil-ice-calendar-swap_{}.html"
    },
    "GCK": {
        "symbol": "GCK",
        "product": "Gold Kilo Futures",
        "group": "metals",
        "base_url": "http://www.cmegroup.com/trading/metals/precious/kilo-gold-futures_{}.html"
    },
    "CAD": {
        "symbol": "CAD",
        "product": "U.S. Dollar / Canadian Dollar Future (USD/CAD) Physically Deliverable Future (CLS Eligible)",
        "group": "products",
        "base_url": "http://www.cmegroup.com/trading/products/fx/majors/usd-cad_{}.html"
    },
    "BIO": {
        "symbol": "BIO",
        "product": "E-mini NASDAQ Biotechnology Index Futures",
        "group": "equity",
        "base_url": "http://www.cmegroup.com/trading/equity-index/us-index/e-mini-nasdaq-biotechnology_{}.html"
    },
    "A33": {
        "symbol": "A33",
        "product": "1% Fuel Oil Rdam (Platts) vs. 1% Fuel Oil NWE (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/1-fuel-oil-rdam-vs-1-fuel-oil-nwe-platts-swap-futures_{}.html"
    },
    "LHV": {
        "symbol": "LHV",
        "product": "NYISO Lower Hudson Valley Capacity Calendar-Month Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/electricity/nyiso-lower-hudson-valley-capacity-calendar-month_{}.html"
    },
    "GOC": {
        "symbol": "GOC",
        "product": "Low Sulphur Gasoil Crack Spread (1000mt) Financial Futures ",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/gasoil-ice-crack-spread-1000mt-swap-futures_{}.html"
    },
    "AFI": {
        "symbol": "AFI",
        "product": "1% Fuel Oil Cargoes FOB NWE (Platts) Crack Spread Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/1pct-fuel-oil-northwest-europe-nwe-crack-spread-swap_{}.html"
    },
    "A1W": {
        "symbol": "A1W",
        "product": "1% Fuel Oil Cargoes CIF MED (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/1-percent-fuel-oil-platts-cargoes-cif-med-swap_{}.html"
    },
    "UCM": {
        "symbol": "UCM",
        "product": "Mini ULSD 10ppm Cargoes CIF MED (Platts) vs. Low Sulphur Gasoil Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/mini-ulsd-10ppm-platts-cargoes-cif-med-vs-gasoil-swap-futures_{}.html"
    },
    "PFS": {
        "symbol": "PFS",
        "product": "Permian Natural Gas (Platts IFERC) Fixed Price Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/natural-gas/permian-natural-gas-fixed-price-swap_{}.html"
    },
    "MAE": {
        "symbol": "MAE",
        "product": "Mini Argus Propane Far East Index Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/petrochemicals/mini-argus-propane-far-east-index-swap_{}.html"
    },
    "MDB": {
        "symbol": "MDB",
        "product": "Mini Dated Brent (Platts) Financial Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/crude-oil/mini-dated-brent-platts-financial_{}.html"
    },
    "ALX": {
        "symbol": "ALX",
        "product": "Los Angeles CARB Diesel (OPIS) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/los-angeles-carb-diesel-opis-outright-swap_{}.html"
    },
    "ABT": {
        "symbol": "ABT",
        "product": "Singapore Fuel Oil 380 cst (Platts) BALMO Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/singapore-380cst-fuel-oil-balmo-swap_{}.html"
    },
    "FT1": {
        "symbol": "FT1",
        "product": "E-mini FTSE 100 Index (GBP) Futures",
        "group": "equity",
        "base_url": "http://www.cmegroup.com/trading/equity-index/international-index/e-mini-ftse-100-index_{}.html"
    },
    "ACM": {
        "symbol": "ACM",
        "product": "Coal (API 5) fob Newcastle (Argus/McCloskey) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/coal/coal-api-5-fob-newcastle-argus-mccloskey_{}.html"
    },
    "AZ7": {
        "symbol": "AZ7",
        "product": "ULSD 10ppm CIF MED (Platts) vs. Low Sulphur Gasoil Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/ulsd-10ppm-cif-med-vs-ice-gasoil-swap-futures_{}.html"
    },
    "EOB": {
        "symbol": "EOB",
        "product": "Argus Gasoline Eurobob Oxy Barges NWE Crack Spread (1000mt) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/argus-gasoline-eurobob-oxy-barges-nwe-crack-spread-1000mt-swap-futures_{}.html"
    },
    "A1X": {
        "symbol": "A1X",
        "product": "1% Fuel Oil Cargoes CIF NWE (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/1-percent-fuel-oil-platts-cargoes-cif-nwe-swap_{}.html"
    },
    "MIR": {
        "symbol": "MIR",
        "product": "E-micro Indian Rupee/USD Futures",
        "group": "fx",
        "base_url": "http://www.cmegroup.com/trading/fx/e-micros/e-micro-indian-rupee_{}.html"
    },
    "AR0": {
        "symbol": "AR0",
        "product": "Mont Belvieu Natural Gasoline (OPIS) BALMO Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/petrochemicals/mt-belvieu-natural-gasoline-balmo-swap_{}.html"
    },
    "AUH": {
        "symbol": "AUH",
        "product": "European 1% Fuel Oil Barges FOB Rdam (Platts) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/european-1pct-fuel-oil-rotterdam-calendar-swap_{}.html"
    },
    "FBT": {
        "symbol": "FBT",
        "product": "FAME 0 Biodiesel FOB Rdam (Argus) (RED Compliant) vs. Low Sulphur Gasoil Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/fame-0-biodiesel-argus-fob-rotterdam-red-compliant-vs-ice-gasoil-spread-swap-futures_{}.html"
    },
    "MGB": {
        "symbol": "MGB",
        "product": "Mini Gasoil 0.1 Barges FOB Rdam (Platts) vs. Low Sulphur Gasoil Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/mini-gasoil-0pt1-barges-fob-rdam-vs-ice-gasoil-swap_{}.html"
    },
    "ARI": {
        "symbol": "ARI",
        "product": "NY RBOB (Platts) vs. RBOB Gasoline Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/new-york-rbob-platts-vs-nymex-rbob-spread-swap-futures_{}.html"
    },
    "63": {
        "symbol": "63",
        "product": "3.5% Fuel Oil Cargoes FOB MED (Platts) vs. 3.5% Fuel Oil Barges FOB Rdam (Platts) BALMO Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/35-fuel-oil-rdam-vs-35-fob-med-spread-platts-balmo-swap-futures_{}.html"
    },
    "FT5": {
        "symbol": "FT5",
        "product": "E-mini FTSE China 50 Index Futures",
        "group": "equity",
        "base_url": "http://www.cmegroup.com/trading/equity-index/international-index/e-mini-ftse-china-50-index_{}.html"
    },
    "A1V": {
        "symbol": "A1V",
        "product": "Jet Aviation Fuel Cargoes FOB MED (Platts) vs. Low Sulphur Gasoil Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/jet-aviation-fuel-platts-cargoes-fob-med-vs-ice-gasoil-swap_{}.html"
    },
    "QC": {
        "symbol": "QC",
        "product": "E-mini Copper Futures",
        "group": "metals",
        "base_url": "http://www.cmegroup.com/trading/metals/base/emini-copper_{}.html"
    },
    "AKZ": {
        "symbol": "AKZ",
        "product": "European Naphtha (Platts) BALMO Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/european-naphtha-balmo-swap_{}.html"
    },
    "MAS": {
        "symbol": "MAS",
        "product": "Mini Argus Propane (Saudi Aramco) Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/petrochemicals/mini-argus-propane-saudi-aramco-swap_{}.html"
    },
    "AWQ": {
        "symbol": "AWQ",
        "product": "Gasoil 0.1 Barges FOB Rdam (Platts) vs. Low Sulphur Gasoil Futures",
        "group": "energy",
        "base_url": "http://www.cmegroup.com/trading/energy/refined-products/gasoil-01-fob-rotterdam-barges-vs-ice-gasoil-swap_{}.html"
    },
}