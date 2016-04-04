import logging
import queue

from hyzou.common.events import *


class Portfolio(object):

    def __init__(self,market,strategy):
        self.all_holdings={}
        self.holdings={}

        self.opening_trade={}
        self.all_trade={}

        # Main events queue shared with Market and Execution
        self.events_queue = queue.PriorityQueue()
        self.market = market
        self.strategy = strategy

        # Grabbing config from strategy
        #[setattr(self, key, val) for key, val in self.strategy.settings.items()]

        #self.risk = RiskAnalysis(self.strategy.settings, self.cash_balance, self.net_liquidation)

    @property
    def long_positions(self):
        return [trade for trade in self.open_trades.values() if trade.direction in ('BUY')]

    @property
    def short_positions(self):
        return [trade for trade in self.open_trades.values() if trade.direction in ('SHORT')]

    def run_cycle(self):
        while True:
            try:
                event = self.events_queue.get(False)
            except queue.Empty:
                break

            if isinstance(event, MarketEvent):
                self.handle_market_event(event)

            elif isinstance(event, SignalEvent):
                logging.debug(str(event))
                self.generate_orders(event)

            elif isinstance(event, OrderEvent):
                logging.debug(str(event))
                self.execute_order(event)

            elif isinstance(event, FillEvent):
                logging.debug(str(event))
                self.update_from_fill(event)

    def handle_market_event(self,event):
        self.market._update_based_on_external_data(event)

        if event.sub_type == 'before_open':
            self.market_opened()
            self.strategy.before_open()

        elif event.sub_type == 'after_close':
            self.market_closed()
            self.strategy.after_close()

        else:
            try:
                if event.sub_type == 'on_open':
                    self.strategy._call_strategy_method('on_open', event.symbol)

                elif event.sub_type == 'during':
                    self.strategy._call_strategy_method('during', event.symbol)

                elif event.sub_type == 'on_close':
                    self.strategy._call_strategy_method('on_close', event.symbol)

            except BarError as e:
                # Problems in market bars or past_bars would raise BarError
                # e.g. nonexisting bars, bars with 0.0 or bars smaller than length
                # requested should be disconsidered
                pass