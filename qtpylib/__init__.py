#!/usr/bin/env python
# -*- coding: utf-8 -*-
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

__version__ = '1.5.55a'
__author__ = 'Ran Aroussi'

from . import *

# make indicators available as pandas extentions
import qtpylib.indicators as indicators

import os
import sys

path = {
    "library": os.path.dirname( os.path.realpath(__file__) ),
    "caller": os.path.dirname( os.path.realpath(sys.argv[0]) )
}

__all__ = [
    'blotter',
    'algo',
    'broker',
    'tools',
    'sms',
    'indicators',
    'talib_indicators',
    'futures',
    'path'
]
