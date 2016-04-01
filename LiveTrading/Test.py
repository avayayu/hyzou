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

import argparse
import datetime

# The above could be sent to an independent module
import backtrader as bt
import backtrader.feeds as btfeeds
import backtrader.indicators as btind
from backtrader.utils import flushfile

import LiveTrading.ibData as ibdata


class EmptyStrategy(bt.Strategy):
    '''
    '''
    params = dict(period=15)

    def __init__(self):
        # To control operation entries
        self.orderid = None

        # Create SMA on 2nd data
        self.sma = btind.MovAv.SMA(self.data, period=self.p.period)

        print('--------------------------------------------------')
        print('Strategy Created')
        print('--------------------------------------------------')

    def prenext(self):
        self.next(frompre=True)

    def next(self, frompre=False):
        txt = ''
        txt += '%d' % len(self)
        dtformat = '%Y-%m-%dT%H:%M:%S.%f'
        txt += ', %s' % self.data.datetime.datetime(0).strftime(dtformat)
        txt += ', %.2f' % self.data.open[0]
        txt += ', %.2f' % self.data.high[0]
        txt += ', %.2f' % self.data.low[0]
        txt += ', %.2f' % self.data.close[0]
        txt += ', %d' % self.data.volume[0]
        txt += ', %d' % self.data.openinterest[0]
        if not frompre:
            txt += ', %.2f' % self.sma[0]
        else:
            txt += ', %.2f' % float('NaN')
        print(txt)

    def start(self):
        print('Datetime, Open, High, Low, Close, Volume, OpenInterest, SMA')


def runstrategy():
    args = parse_args()

    # Create a cerebro
    cerebro = bt.Cerebro()

    # Create the 1st data
    data = ibdata.IBData(dataname=args.data,
                         useRT=args.rtbar,
                         _debug=args.debug)

    if args.replay:
        cerebro.replaydata(dataname=data,
                           timeframe=bt.TimeFrame.Minutes,
                           compression=1)
    elif args.resample:
        cerebro.resampledata(dataname=data,
                             timeframe=bt.TimeFrame.Seconds,
                             compression=5)
    else:
        cerebro.adddata(data)

    # Add the strategy
    cerebro.addstrategy(EmptyStrategy, period=args.period)

    # Live data ... avoid long data accumulation by switching to "exactbars"
    cerebro.run(exactbars=True)


def parse_args():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description='IB Realtime Data Feed')

    parser.add_argument('--data', '-d',
                        default='IBKR-STK-SMART',
                        help='data into the system')

    parser.add_argument('--rtbar', required=False, action='store_true',
                        help=('Use 5 seconds real time bar updates'))

    parser.add_argument('--debug', required=False, action='store_true',
                        help=('Display all info received form IB'))

    parser.add_argument('--period', '-p', default=5, type=int,
                        help='Period to apply to the Simple Moving Average')

    pgroup = parser.add_mutually_exclusive_group(required=False)

    pgroup.add_argument('--replay', required=False, action='store_true',
                        help=('replay the data on a 1 minute basis'))

    pgroup.add_argument('--resample', required=False, action='store_true',
                        help=('resample the data on a 1 minute basis'))

    return parser.parse_args()


if __name__ == '__main__':
    runstrategy()