import datetime
import inspect
import logging
from math import floor
import os
import sys
import queue

import numpy as np

from hyzou.LiveTrading import settings, utils
from hyzou.common.events import SignalEvent


class Strategy(object):

    def __init__(self,*args,**kwargs):
        self._args=args
        self._kwargs=kwargs

        self.initialize()

        self.symbol_status = {s:SymbolStatus() for s in self.SYMBOL_LIST}
        self._subscribed_symbols = set()
        self._unsubscribe_all = False

        self.settings = {}
        self.settings['SYMBOL_LIST'] = getattr(self, 'SYMBOL_LIST', [])
        self.settings['DATE_FROM'] = getattr(self, 'DATE_FROM', datetime.datetime.now() - datetime.timedelta(weeks=52))
        self.settings['DATE_TO'] = getattr(self, 'DATE_TO', datetime.datetime.now())

        self.settings['EXCHANGE'] = getattr(self, 'EXCHANGE', settings.EXCHANGE)
        self.settings['SUB_EXCHANGE'] = getattr(self, 'EXCHANGE', settings.SUB_EXCHANGE)
        self.settings['CURRENCY'] = getattr(self, 'CURRENCY', settings.CURRENCY)
        self.settings['SEC_TYPE'] = getattr(self, 'SEC_TYPE', settings.SEC_TYPE)
        self.settings['NORMALIZE_PRICES'] = getattr(self, 'NORMALIZE_PRICES', settings.NORMALIZE_PRICES)
        self.settings['NORMALIZE_VOLUME'] = getattr(self, 'NORMALIZE_VOLUME', settings.NORMALIZE_VOLUME)
        self.settings['INITIAL_CAPITAL'] = getattr(self, 'INITIAL_CAPITAL', settings.INITIAL_CAPITAL)
        self.settings['CAPITAL_TRADABLE_CAP'] = getattr(self, 'CAPITAL_TRADABLE_CAP', settings.CAPITAL_TRADABLE_CAP)
        self.settings['ROUND_LOT_SIZE'] = getattr(self, 'ROUND_LOT_SIZE', settings.ROUND_LOT_SIZE)
        self.settings['COMMISSION_FIXED'] = getattr(self, 'COMMISSION_FIXED', settings.COMMISSION_FIXED)
        self.settings['COMMISSION_PCT'] = getattr(self, 'COMMISSION_PCT', settings.COMMISSION_PCT)
        self.settings['COMMISSION_MIN'] = getattr(self, 'COMMISSION_MIN', settings.COMMISSION_MIN)
        self.settings['MAX_SLIPPAGE'] = getattr(self, 'MAX_SLIPPAGE', settings.MAX_SLIPPAGE)
        self.settings['MAX_LONG_POSITIONS'] = floor(getattr(self, 'MAX_LONG_POSITIONS', settings.MAX_LONG_POSITIONS))
        self.settings['MAX_SHORT_POSITIONS'] = floor(getattr(self, 'MAX_SHORT_POSITIONS', settings.MAX_SHORT_POSITIONS))
        self.settings['POSITION_SIZE'] = getattr(self, 'POSITION_SIZE', 1.0/self.settings['MAX_LONG_POSITIONS'] if self.settings['MAX_LONG_POSITIONS'] else 1.0/self.settings['MAX_SHORT_POSITIONS'])
        self.settings['ADJUST_POSITION_DOWN'] = getattr(self, 'ADJUST_POSITION_DOWN', settings.ADJUST_POSITION_DOWN)
        self.settings['THRESHOLD_DANGEROUS_TRADE'] = getattr(self, 'THRESHOLD_DANGEROUS_TRADE', settings.THRESHOLD_DANGEROUS_TRADE)
        self.settings['ROUND_DECIMALS'] = getattr(self, 'ROUND_DECIMALS', settings.ROUND_DECIMALS)
        self.settings['ROUND_DECIMALS_BELOW_ONE'] = getattr(self, 'ROUND_DECIMALS_BELOW_ONE', settings.ROUND_DECIMALS_BELOW_ONE)
        self.settings['SYMBOL_SUFFIX'] = getattr(self, 'SYMBOL_SUFFIX', settings.SYMBOL_SUFFIX)
        self.settings['HISTORICAL_DATA_SOURCE'] = getattr(self, 'HISTORICAL_DATA_SOURCE', settings.HISTORICAL_DATA_SOURCE)

    def initialize(self):
        pass

    def before_open(self):
        pass

    def after_close(self):
        pass

    def get_arg(self, index, default=None):
        if isinstance(index, int):
            try:
                return self._args[index]
            except IndexError:
                return default

        elif isinstance(index, str):
            try:
                return self.kwargs[index]
            except KeyError:

                return default
    def __str__(self):
        return self.__class__.__name__ + "(" + ",".join([str(i) for i in self._args]) + ")"

    def buy(self, symbol, price=None, exit_price=None):
        if self.is_neutral(symbol):
            self._signal_dispatcher('BUY', symbol, price, exit_price)

    def sell(self, symbol, price=None, exit_price=None):
        if self.is_long(symbol):
            self._signal_dispatcher('SELL', symbol, price, exit_price)

    def short(self, symbol, price=None, exit_price=None):
        if self.is_neutral(symbol):
            self._signal_dispatcher('SHORT', symbol, price, exit_price)

    def cover(self, symbol, price=None, exit_price=None):
        if self.is_short(symbol):
            self._signal_dispatcher('COVER', symbol, price, exit_price)

    def _signal_dispatcher(self, direction, symbol, price, exit_price):
        if direction not in ('BUY', 'SELL', 'SHORT', 'COVER'):
            raise ValueError("Operation needs to be BUY, SELL, SHORT or COVER.")

        price = price or self.market.last_price(symbol)

        if direction in ('BUY', 'SHORT') and exit_price:
            estimated_profit = self.trade_profitability(direction, price, exit_price)
            sig = SignalEvent(symbol, direction, price, exit_price, estimated_profit)
        else:
            sig = SignalEvent(symbol, direction, price)

        self.symbol_status[symbol].update(direction, price)
        self.events_queue.put(sig)

    def _market_opened(self):
        # Restart symbol subscriptions
        self._subscribed_symbols = set()
        self._unsubscribe_all = False

    def _call_strategy_method(self, method_name, symbol=None):
        method = getattr(self, method_name)
        if symbol:
            if self.is_subscribed_to(symbol):
                method(symbol)
        else:
            method()

    def before_open(self):
        # Should be overloaded by each strategy algorithm
        pass

    def on_open(self, symbol):
        # Should be overloaded by each strategy algorithm
        pass

    def during(self, symbol):
        # Should be overloaded by each strategy algorithm
        pass

    def on_close(self, symbol):
        # Should be overloaded by each strategy algorithm
        pass

    def after_close(self):
        # Should be overloaded by each strategy algorithm
        pass

    def after_backtest(self, performance):
        # Should be overloaded by each strategy algorithm
        pass

    @property
    def long_symbols(self):
        return [s for s in self.symbol_status if self.symbol_status[s].direction == 'BUY']

    @property
    def short_symbols(self):
        return [s for s in self.symbol_status if self.symbol_status[s].direction == 'SHORT']

    def is_long(self, symbol):
        return True if self.symbol_status[symbol].direction == 'BUY' else False

    def is_short(self, symbol):
        return True if self.symbol_status[symbol].direction == 'SHORT' else False

    def is_neutral(self, symbol):
        return True if self.symbol_status[symbol].direction == '' else False

    @property
    def subscribed_symbols(self):
        return self._subscribed_symbols if self._subscribed_symbols else set(self.market.symbol_list)

    def is_subscribed_to(self, symbol):
        if not self._unsubscribe_all and symbol in self.subscribed_symbols:
            return True
        return False

    def subscribe(self, symbol):
        """ Subscribes to a specific symbol. If left untouched strategy will
        subscribe to all symbols in SYMBOL_LIST """
        self._subscribed_symbols.add(symbol)

    def unsubscribe(self, symbol_to_remove=None):
        """ Unsubscribes from symbol. Unsubscribes from all symbols if symbol_to_remove is None. """
        if not symbol_to_remove:
            self._unsubscribe_all = True
        else:
            # If _subscribed_symbols is empty, we must fill it with symbol_list and then
            # remove symbol
            if not self._subscribed_symbols:
                self._subscribed_symbols = set(self.market.symbol_list)
            self._subscribed_symbols.remove(symbol_to_remove)

    def trade_profitability(self, direction, entry_price, exit_price):
        """ Checks if, given an entry and exit price, a trade would be profitable.
        Uses same methods from risk that are used to calculate position size by
        portfolio.
        """
        quantity, entry_comm = self.risk.calculate_quantity_and_commission(direction, entry_price)
        exit_comm = self.risk.determine_commission(quantity, exit_price)
        total_comm = entry_comm + exit_comm
        return (exit_price - entry_price)*quantity - total_comm

class SymbolStatus(object):
    def __init__(self, direction=''):
        self.direction = direction
        self.entry_price = None
        self.exit_price = None

    def update(self, direction, price):
        self.direction = direction if direction in ('BUY', 'SHORT') else ''
        # Update entry price if BUY or SHORT
        self.entry_price = price if direction in ('BUY', 'SHORT') else self.entry_price
        # Update exit_price if SELL or COVER
        self.exit_price = price if direction in ('SELL', 'COVER') else self.exit_price

        self.updated_at = datetime.datetime.now()

    def __str__(self):
        return self.direction