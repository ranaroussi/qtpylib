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

import sys
import configparser

from nexmo import Client as nexmoClient
from twilio.rest import Client as twilioClient

from qtpylib import (
    path, tools
)

# =============================================
# check min, python version
if sys.version_info < (3, 4):
    raise SystemError("QTPyLib requires Python version >= 3.4")
# =============================================

# ---------------------------------------------
# sms service / credentials
# ---------------------------------------------
SMS_SERVICE = None
SMS_CREDENTIALS = None

sms_ini = configparser.ConfigParser()
sms_ini.read(path['caller'] + '/sms.ini')
sms_data = sms_ini.sections()
if sms_data:
    SMS_SERVICE = sms_data[0].lower().strip()
    SMS_CREDENTIALS = sms_ini[sms_data[0]]


# ---------------------------------------------

def send_text(msg, numbers):

    numbers = _ready_to_send(numbers)
    if not numbers:
        return

    if SMS_SERVICE == "nexmo":
        try:
            _send_nexmo(msg, numbers)
        except Exception as e:
            pass

    elif SMS_SERVICE == "twilio":
        try:
            _send_twilio(msg, numbers)
        except Exception as e:
            pass


# ---------------------------------------------

def _send_trade(trade, numbers, timezone="UTC"):

    numbers = _ready_to_send(numbers)
    if not numbers:
        return

    # decimals to round:
    decimals = max([2, len(str(trade['entry_price']).split('.')[1])])

    # reverse direction for exits
    if trade['action'] == "EXIT":
        trade['direction'] = "BUY" if trade['direction'] == "SELL" else "BUY"

    # message template
    arrow = "▲" if trade['direction'] == "BUY" else "▼"
    order_type = trade['order_type'].replace(
        "MARKET", "MKT").replace("LIMIT", "LMT")

    msg = ""

    trade['direction'] = trade['direction'].replace(
        "BUY", "BOT").replace("SELL", "SLD")

    qty = ""
    if abs(trade['quantity']) > 1:
        qty = str(abs(trade['quantity'])) + "x "

    if trade['action'] == "ENTRY":
        target = round(trade['target'],
                       decimals) if trade['target'] > 0 else '-'
        stop = round(trade['stop'], decimals) if trade['stop'] > 0 else '-'

        try:
            trade['entry_time'] = tools.datetime_to_timezone(
                trade['entry_time'], timezone)
            msg += trade['entry_time'].strftime('%H:%M:%S%z') + "\n"
        except Exception as e:
            pass

        msg += trade['direction'] + " " + arrow + \
            " " + qty + " " + trade['symbol']
        msg += " @ " + str(round(trade['entry_price'], decimals))
        msg += " " + order_type + "\n"
        msg += "TP " + str(target) + " / SL " + str(stop) + "\n"

    elif trade['action'] == "EXIT":
        exit_type = trade['exit_reason'
                          ].replace("TARGET", "TGT"
                                    ).replace("STOP", "STP"
                                              ).replace("SIGNAL", order_type)
        pnl_char = "+" if trade['realized_pnl'] > 0 else ""

        try:
            trade['exit_time'] = tools.datetime_to_timezone(
                trade['entry_time'], timezone)
            msg += trade['exit_time'].strftime('%H:%M:%S%z') + "\n"
        except Exception as e:
            pass

        msg += trade['direction'] + " " + arrow + \
            " " + qty + " " + trade['symbol']
        msg += " @ " + str(round(trade['exit_price'], decimals))
        msg += " " + exit_type + "\n"
        msg += "PL " + pnl_char + str(round(trade['realized_pnl'], decimals))
        msg += " (" + trade['duration'] + ")\n"

    # if UTC remove timezone info
    msg = msg.replace("+0000", " UTC")

    # send sms
    send_text(msg, numbers)


# ---------------------------------------------

def _ready_to_send(numbers):

    # get credentials
    if SMS_SERVICE is None:
        return False

    if numbers is None:
        return False

    # return
    if not isinstance(numbers, list):
        numbers = [numbers]

    if not numbers:
        return False

    return numbers


# ---------------------------------------------

def _send_nexmo(msg, numbers):

    nexmo_key = SMS_CREDENTIALS['key'].strip().split(
        ' ')[0] if "key" in SMS_CREDENTIALS else None

    nexmo_secret = SMS_CREDENTIALS['secret'].strip().split(
        ' ')[0] if "secret" in SMS_CREDENTIALS else None

    nexmo_from = SMS_CREDENTIALS['from'].strip().split(
        ' ')[0] if "from" in SMS_CREDENTIALS else "QTPyLib"

    if nexmo_key is None or nexmo_secret is None or nexmo_from is None:
        return 0

    # send message
    msg = {'type': 'unicode', 'from': nexmo_from, 'to': '', 'text': msg}

    # send message
    sent = 0
    smsClient = nexmoClient(key=nexmo_key, secret=nexmo_secret)
    for number in numbers:
        if "+" not in number:
            number = "+" + str(number)
        msg['to'] = number
        response = smsClient.send_message(msg)
        if response['messages'][0]['status'] == '0':
            sent += 1

    return len(numbers) == sent


# ---------------------------------------------

def _send_twilio(msg, numbers):

    twilio_sid = SMS_CREDENTIALS['sid'].strip().split(
        ' ')[0] if "sid" in SMS_CREDENTIALS else None

    twilio_token = SMS_CREDENTIALS['token'].strip().split(
        ' ')[0] if "token" in SMS_CREDENTIALS else None

    twilio_from = SMS_CREDENTIALS['from'].strip().split(
        ' ')[0] if "from" in SMS_CREDENTIALS else "QTPyLib"

    if twilio_sid is None or twilio_token is None or twilio_from is None:
        return 0

    # send message
    sent = 0
    smsClient = twilioClient(twilio_sid, twilio_token)
    for number in numbers:
        if "+" not in number:
            number = "+" + str(number)
        response = smsClient.messages.create(
            body=msg, to=number, from_=twilio_from)
        if response.sid != '':
            sent += 1

    return len(numbers) == sent
