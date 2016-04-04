#!/usr/bin/env python
# -*- coding: utf-8; py-indent-offset:4 -*-
###############################################################################
#
# Copyright (C) 2015,2016 Daniel Rodriguez
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from datetime import datetime
import itertools
import time
import threading

from twspy.ib.Contract import Contract
import twspy.ib as ibopt

from backtrader.feed import DataBase
from backtrader import TimeFrame, date2num
from backtrader.utils.py3 import bytes, queue, with_metaclass


class ItemContainer(object):
    def __init__(self, **kwargs):
        for key, val in kwargs.items():
            setattr(self, key, val)


def _ts2dt(tstamp=None):
    if not tstamp:
        return datetime.utcnow()  # or .now() ??

    sec, msec = divmod(int(tstamp), 1000)
    usec = msec * 1000
    return datetime.fromtimestamp(sec).replace(microsecond=usec)


class RTVolume(object):
    '''
    Parses a tickString tickType 48 (RTVolume) event from the IB API into its
    constituent fields

    Supports using a "price" to simulate an RTVolume from a price event
    '''
    _fields = [
        ('price', float),
        ('size', int),
        ('datetime', _ts2dt),
        ('volume', int),
        ('vwap', float),
        ('single', bool)
    ]

    def __init__(self, rtvol='', price=None):
        # Use a provided string or simulate a list of empty tokens
        tokens = iter(rtvol.split(';'))

        # Put the tokens as attributes using the corresponding func
        for name, func in self._fields:
            setattr(self, name, func(next(tokens)) if rtvol else func())

        # If price was provided use it
        if price is not None:
            self.price = price


class MetaSingleton(type):
    '''
    Metaclass to make a metaclassed class a singleton
    '''
    def __init__(cls, name, bases, dct):
        super(MetaSingleton, cls).__init__(name, bases, dct)
        cls.instance = None

    def __call__(cls, *args, **kwargs):
        if cls.instance is None:
            cls.instance = super(MetaSingleton, cls).__call__(*args, **kwargs)
        return cls.instance


class IBPy(with_metaclass(MetaSingleton, object)):
    '''
    Singleton class wrapping an ibpy ibConnection instance.

    begin/end use a ref count mechanism to ensure connect/disconnect only take
    place once (and register/unregister too)
    '''
    _lock = threading.Lock()  # sync access to _tickerId counter
    _tickerId = itertools.count(1)  # unique tickerIds

    def __init__(self, *args, **kwargs):
        super(IBPy, self).__init__()

        self._debug = kwargs.pop('_debug', False)

        self.conn = ibopt.ibConnection(**kwargs)  # ibpy connection object
        self.ccount = 0  # ref count for connect/disconnect register/unregister

        self.qs = dict()  # key: tickerId -> queues
        self.ts = dict()  # key: queue -> tickerId
        self.iscash = set()  # tickerIds

    def begin(self):
        with self._lock:
            if not self.ccount:
                self.conn.register(self.tickString, ibopt.message.tickString)
                self.conn.register(self.tickPrice, ibopt.message.tickPrice)
                self.conn.register(self.realtimeBar, ibopt.message.realtimeBar)

                if self._debug:
                    self.conn.registerAll(self.watcher)

                self.conn.connect()

            self.ccount += 1

    def end(self):
        with self._lock:
            self.ccount -= 1
            if not self.ccount:
                self.conn.unregister(self.tickString, ibopt.message.tickString)
                self.conn.unregister(self.tickPrice, ibopt.message.tickPrice)
                self.conn.unregister(self.realtimeBar,
                                     ibopt.message.realtimeBar)

                if self._debug:
                    self.conn.unregisterAll(self.watcher)

                self.conn.disconnect()

    def nextTickerId(self):
        with self._lock:
            tickerId = next(self._tickerId)
        return tickerId

    def getQueue(self, tickerId):
        self.qs[tickerId] = q = queue.Queue()
        self.ts[q] = tickerId

        return q

    def getTickerQueue(self):
        tickerId = self.nextTickerId()
        q = self.getQueue(tickerId)
        return tickerId, q

    def cancelQueue(self):
        # pop ts (tickers) and with the result qs (queues)
        tickerId = self.ts.pop(q, None)
        self.qs.pop(tickerId, None)
        # sets don't have a pop with default argument
        if tickerId in self.iscash:
            self.iscash.remove(tickerId)

    def reqHistoricalData(self, contract, enddate, barsize, duration,
                          useRTH=False):

        tickerId, q = self.getTickerQueue()

        enddate_str = num2date(enddate).strftime('%Y%m%d %H:%M:%S')

        self.conn.reqHistoricalData(
            tickerId,
            contract,
            enddate_str,
            duration,
            barsize,
            bytes('TRADES'),
            int(useRTH))

        return q

    def cancelHistoricalData(self, q):
        self.conn.cancelHistoricalData(self.ts[q])
        self.cancelQueue(q)

    def reqRealTimeBars(self, contract, useRTH=False, duration=5):
        '''
        Creates a request for (5 seconds) Real Time Bars

        Params:
          - contract: a ib.ext.Contract.Contract intance

        Returns:
          - a Queue the client can wait on to receive a RTVolume instance
        '''
        tickerId, q = self.getTickerQueue()

        # 20150929 - Only 5 secs supported for duration
        self.conn.reqRealTimeBars(
            tickerId,
            contract,
            duration,
            bytes('TRADES'),
            int(useRTH))

        return q

    def cancelRealTimeBars(self, q):
        '''
        Cancels an existing MarketData subscription

        Params:
          - q: the Queue returned by reqMktData
        '''
        self.conn.cancelRealTimeBars(self.ts[q])
        self.cancelQueue(q)

    def reqMktData(self, contract):
        '''
        Creates a MarketData subscription

        Params:
          - contract: a ib.ext.Contract.Contract intance

        Returns:
          - a Queue the client can wait on to receive a RTVolume instance
        '''
        tickerId, q = self.getTickerQueue()
        ticks = '233'  # request RTVOLUME tick delivered over tickString

        if contract.m_secType == 'CASH':
            self.iscash.add(tickerId)
            ticks = ''  # cash markets do not get RTVOLUME

        # Can request 233 also for cash ... nothing will arrive
        self.conn.reqMktData(tickerId, contract, bytes(ticks), False)
        return q

    def cancelMktData(self, q):
        '''
        Cancels an existing MarketData subscription

        Params:
          - q: the Queue returned by reqMktData
        '''
        self.conn.cancelMktData(self.ts[q])
        self.cancelQueue(q)

    def tickString(self, msg):
        if msg.tickType == 48:  # RTVolume
            try:
                rtvol = RTVolume(msg.value)
            except ValueError:  # price not in message ...
                pass
            else:
                self.qs[msg.tickerId].put(rtvol)

    def tickPrice(self, msg):
        '''
        Cash Markets have no notion of "last_price"/"last_size" and the
        tracking of the price is done (industry de-facto standard at least with
        the IB API) following the BID price

        A RTVolume which will only contain a price is put into the client's
        queue to have a consistent cross-market interface
        '''
        # Used for "CASH" markets
        if msg.tickerId in self.iscash:
            if msg.field == 1:  # Bid Price
                try:
                    rtvol = RTVolume(price=msg.price)
                except ValueError:  # price not in message ...
                    pass
                else:
                    self.qs[msg.tickerId].put(rtvol)

    def realtimeBar(self, msg):
        '''
        Receives x seconds Real Time Bars (at the time of writing only 5
        seconds are supported)

        Not valid for cash markets
        '''
        msg.time = datetime.fromtimestamp(msg.time)
        self.qs[msg.reqId].put(msg)

    def historicalData(self, msg):
        if msg.time.startswith('finished-'):
            msg = None
        else:
            msg.time = datetime.fromtimestamp(msg.time)

        self.qs[msg.reqId].put(msg)

    def watcher(self, msg):
        print(msg)


class IBData(DataBase):
    params = (
        ('useRT', True),
        ('host', '127.0.0.1'),
        ('port', 7496),
        ('clientId', 0),
        ('exchange', 'SMART'),  # usual industry value
        ('currency', ''),
        ('_debug', False),
    )

    def __init__(self):
        self.ib = IBPy(host=self.p.host,
                       port=self.p.port,
                       clientId=self.p.clientId,
                       _debug=self.p._debug)

        self.parsecontract()

    def parsecontract(self):
        '''Formats:
          - TICKER-STK-EXCHANGE  # Stock
          - TICKER-STK-EXCHANGE-CURRENCY  # Stock

          - TICKER-IND-EXCHANGE  # Index
          - TICKER-IND-EXCHANGE-CURRENTCY  # Index

          - TICKER-YYYYMM-EXCHANGE-CURRENCY  # Future
          - TICKER-YYYYMM-EXCHANGE-CURRENCY-MULTIPLIER  # Future

          - TICKER-YYYYMM-EXCHANGE-CURRENCY-RIGHT-STRIKE  # FOP
          - TICKER-YYYYMM-EXCHANGE-CURRENCY-RIGHT-STRIKE-MULT  # FOP

          - CUR1.CUR2-CASH-IDEALPRO  # Forex

          - TICKER-YYYYMMDD-EXCHANGE-CURRENCY-RIGHT-STRIKE  # OPT
          - TICKER-YYYYMMDD-EXCHANGE-CURRENCY-RIGHT-STRIKE-MULT  # OPT
        '''
        # Set defaults for optional tokens in the ticker string
        exch = self.p.exchange
        curr = self.p.currency
        expiry = ''
        strike = 0.0
        right = ''
        mult = ''

        # split the ticker string
        tokens = iter(self.p.dataname.split('-'))

        # Symbol and security type are compulsory
        symbol = next(tokens)
        sectype = next(tokens)

        # security type can be an expiration date
        if sectype.isdigit():
            expiry = sectype  # save the expiration ate

            if len(sectype) == 6:  # YYYYMM
                sectype = 'FUT'
            else:  # Assume OPTIONS - YYYYMMDD
                sectype = 'OPT'

        if sectype == 'CASH':  # need to address currency for Forex
            symbol, curr = symbol.split('.')

        # See if the optional tokens were provided
        try:
            exch = next(tokens)  # on exception it will be the default
            curr = next(tokens)  # on exception it will be the default

            if sectype == 'FUT':
                if not expiry:
                    expiry = next(tokens)
                mult = next(tokens)

                # Try to see if this is FOP - Futures on OPTIONS
                right = next(tokens)
                # if still here this is a FOP and not a FUT
                sectype = 'FOP'
                strike, mult = float(mult), ''  # assign to strike and void

                mult = next(tokens)  # try again to see if there is any

            elif sectype == 'OPT':
                if not expiry:
                    expiry = next(tokens)
                strike = float(next(tokens))  # on exception - default
                right = next(tokens)  # on exception it will be the default

                mult = next(tokens)  # ?? no harm in any case

        except StopIteration:
            pass

        # Make the contract
        self.contract = self.makecontract(
            symbol=symbol, sectype=sectype, exch=exch, curr=curr,
            expiry=expiry, strike=strike, right=right, mult=mult)

        self.cashtype = sectype == 'CASH'

    def start(self):
        '''
        Starts the IB connecction and subscribes to real time data
        '''
        super(IBData, self).start()
        self.ib.begin()
        if not self.p.useRT or self.cashtype:
            self.q = self.ib.reqMktData(self.contract)
        else:
            self.q = self.ib.reqRealTimeBars(self.contract)

    def stop(self):
        '''
        Cancels the Market Data subscription and disconnects
        '''
        super(IBData, self).start()
        if not self.p.useRT or self.cashtype:
            self.ib.cancelMktData(self.q)
        else:
            self.ib.cancelRealTimeBars(self.q)

        self.ib.end()

    def _load(self):
        # sit on the queue waiting for an event
        msg = self.q.get()
        if msg is None:
            return False

        if self.p.useRT:
            return self._load_rtbar(msg)

        return self._load_rtvolume(msg)

    def _load_rtbar(self, rtbar):
        # Datetime transformation
        self.lines.datetime[0] = date2num(rtbar.time)

        # Put the tick into the bar
        self.lines.open[0] = rtbar.open
        self.lines.high[0] = rtbar.high
        self.lines.low[0] = rtbar.low
        self.lines.close[0] = rtbar.close
        self.lines.volume[0] = rtbar.volume
        self.lines.openinterest[0] = 0

        return True

    def _load_rtvolume(self, rtvol):
        # Datetime transformation
        self.lines.datetime[0] = date2num(rtvol.datetime)

        # Put the tick into the bar
        tick = rtvol.price
        self.lines.open[0] = tick
        self.lines.high[0] = tick
        self.lines.low[0] = tick
        self.lines.close[0] = tick
        self.lines.volume[0] = rtvol.size
        self.lines.openinterest[0] = 0

        return True

    def makecontract(self, symbol, sectype, exch, curr,
                     expiry='', strike=0.0, right='', mult=1):
        '''returns a contract from the parameters without check'''

        contract = Contract()
        contract.m_symbol = bytes(symbol)
        contract.m_secType = bytes(sectype)
        contract.m_exchange = bytes(exch)
        if curr:
            contract.m_currency = bytes(curr)
        if sectype in ['FUT', 'OPT', 'FOP']:
            contract.m_expiry = bytes(expiry)
        if sectype in ['OPT', 'FOP']:
            contract.m_strike = strike
            contract.m_right = bytes(right)
        if mult:
            contract.m_multiplier = bytes(mult)
        return contract

    # allowed barsizes and maximum durations (doc-wise)
    _sizeduration = {
        TimeFrame.Seconds: {
            1: ('1 secs', '1800 S'),
            5: ('5 secs', '7200 S'),
            10: ('10 secs', '14400 S'),
            15: ('15 secs', '14400 S'),
            30: ('30 secs', '28800 S'),
            },

        TimeFrame.Minutes: {
            1: ('1 mins', '1 D'),
            2: ('2 mins', '2 D'),
            3: ('3 mins', '1 W'),
            5: ('5 mins', '1 W'),
            10: ('10 mins', '1 W'),
            15: ('15 mins', '2 W'),
            20: ('20 mins', '2 W'),
            30: ('30 mins', '1 M'),
            60: ('1 hour', '1 M'),
            120: ('1 hour', '1 M'),
            180: ('1 hour', '1 M'),
            240: ('1 hour', '1 M'),
            480: ('1 hour', '1 M'),
            },

        TimeFrame.Days: {
            1: ('1 day', '1 Y'),
            },

        TimeFrame.Months: {
            1: ('1 W', '1 Y'),
            },

        TimeFrame.Months: {
            1: ('1 M', '1 Y'),
            },
        }