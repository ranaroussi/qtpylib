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

import datetime
import calendar
import pandas as pd

import pandas.tseries.holiday as _holiday
import pandas.tseries.offsets as _offsets


class _NYSECalendar(_holiday.AbstractHolidayCalendar):
    rules = [
        _holiday.Holiday('New Years Day', month=1, day=1,
                         observance=_holiday.nearest_workday),
        _holiday.USMartinLutherKingJr,
        _holiday.USPresidentsDay,
        _holiday.GoodFriday,
        _holiday.USMemorialDay,
        _holiday.Holiday('USIndependenceDay', month=7, day=4,
                         observance=_holiday.nearest_workday),
        _holiday.USLaborDay,
        _holiday.USThanksgivingDay,
        _holiday.Holiday('Christmas', month=12, day=25,
                         observance=_holiday.nearest_workday)
    ]


def month_day_range(date=None):
    """
    For a date 'date' returns the start and end date for the month of 'date'.
    >>> date = datetime.date(2011, 2, 15)
    >>> month_day_range(date)
    (datetime.date(2011, 2, 1), datetime.date(2011, 2, 28))
    """
    if not date:
        date = datetime.datetime.now()
    first_day = date.replace(day=1)
    last_day = date.replace(day=calendar.monthrange(date.year, date.month)[1])
    return first_day.date(), last_day.date()


def month_trading_dates(date=None):
    first, last = month_day_range(date)
    cal = _NYSECalendar()
    holidays = cal.holidays(first, last).date
    gross_days = pd.date_range(first, last, freq=_offsets.BDay()).date
    net_days = [d for d in gross_days if d not in holidays]
    return pd.DatetimeIndex(net_days)


def month_trading_days(date=None):
    return [day.day for day in month_trading_dates().date]


def is_trading_day(date=None):
    if date is None:
        date = datetime.datetime.now()
    return date.date() in month_trading_dates(date)


def days_passed_in_month():
    dtix = month_trading_dates().date
    return len(dtix[dtix <= datetime.datetime.now().date()])


def days_left_in_month():
    dtix = month_trading_dates().date
    return len(dtix[dtix >= datetime.datetime.now().date()])
