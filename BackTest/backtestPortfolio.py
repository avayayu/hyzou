import datetime
import logging
from math import fsum

from common.events import FillEvent
from common.portfolio import Portfolio

class BacktestPortfolio(Portfolio):

    def cash_balance(self):  # needs to be method because of risk.py
        # Pending orders that remove cash from account
        money_held = fsum([t.quantity*t.estimated_cost for t in self.open_trades.values() if t.direction in ('BUY','COVER') and not t.entry_is_fully_filled])
        return self.holdings['cash'] - money_held

    def net_liquidation(self):  # needs to be method because of risk.py
        market_value = fsum([self.open_trades[s].entry_filled_quantity * self.market.last_price(s) for s in self.open_trades])

        return self.holdings['cash'] + market_value

    def check_signal_consistency(self, symbol, signal_price, direction):
        high = self.market.high(symbol)
        low =self.market.low(symbol)

        if signal_price > high or signal_price < low:
            raise ValueError("You're trying to execute with a price that is out of band today. Strategy {}, date {}, symbol {}, direction {}, exec_price {}, high {}, low {}".format(
                self.strategy, self.market.updated_at, symbol, direction, signal_price, high, low,
            ))
        super(BacktestPortfolio, self).check_signal_consistency(symbol, signal_price, direction)


    def market_opened(self):
        cur_datetime = self.market.updated_at

        #self.market.is_market_opened = True

        # If there is no current holding, meaning execution just started
        if not self.holdings:
            self.holdings = self.construct_holding(cur_datetime, self.INITIAL_CAPITAL, 0.00, self.INITIAL_CAPITAL)

        else:
            if  cur_datetime <= self.holdings['datetime']:
                raise ValueError("New bar arrived with same datetime as previous holding. Aborting!")

            # Add current holdings to all_holdings lists
            self.all_holdings.append(self.holdings)

            self.holdings = self.construct_holding(
                cur_datetime,
                self.holdings['cash'],
                self.holdings['commission'],
                self.holdings['total'],
            )

        self.strategy._market_opened()

    def market_closed(self):

        if not all([t.entry_is_fully_filled for t in self.open_trades.values()]):
            logging.warning("Market closed while there are pending orders. Shouldn't happen in backtesting.")

        #self.market.is_market_opened=False

        # open_trades used for keeping track of open trades over time
        self.holdings['open_trades'] = len(self.open_trades)
        # subscribed_symbols used for keeping track of how many
        # symbols were subscribed to each day
        if self.strategy._unsubscribe_all:
            self.holdings['subscribed_symbols'] = 0
        else:
            if self.strategy.subscribed_symbols:
                self.holdings['subscribed_symbols'] = len(self.strategy.subscribed_symbols)
            else:
                self.holdings['subscribed_symbols'] = len(self.market.symbol_list)

        # Restarts holdings 'total' and s based on this_close price and current_position[s]
        self.holdings['total'] = self.net_liquidation()

        self.verify_portfolio_consistency()

    def get_next_order_id(self):
        this_order_id = getattr(self, 'next_order_id', 0)
        self.next_order_id = this_order_id + 1
        return this_order_id

    def execute_order(self, order):
        # Calls execute_order from parent (Portfolio in common/portfolio.py)
        super(BacktestPortfolio, self).execute_order(order)

        # Simulated order execution below
        commission = self.risk.determine_commission(order.quantity, order.limit_price)
        # in case I mess up and remove abs() again
        assert(commission>=0)
        # Fake fill
        fill_event = FillEvent(
            order.symbol,
            order.direction,
            order.quantity,
            order.limit_price,
            commission,
        )
        self.events_queue.put(fill_event)

    def update_from_fill(self, fill):
        trade = self.open_trades[fill.symbol]

        if trade.is_fill_relevant_to_portfolio(fill):
            #每一次真实的交易后就将前一次holding加入all_holdings列表
            self.all_holdings.append(self.holdings)
            self.holdings['commission'] += fill.commission
            self.holdings['cash'] -= (fill.quantity * fill.avg_cost + fill.commission)

            #self.holdings['datetime']=self.market._data[fill.symbol]['updated_at']

        trade.update_from_fill(fill, fake_exited_at=self.market.updated_at)

        #self.holdings['total'] = self.net_liquidation()

        self.archive_trade_if_exited(fill)

    def update_last_holdings(self):
        # Adds latest current position and holding into 'all' lists, so they
        # can be part of performance as well
        if self.holdings:
            self.all_holdings.append(self.holdings)
            self.holdings, self.positions = None, None

        # "Fake close" trades that are open, so they can be part of trades performance stats
        for trade in self.open_trades.values():

            direction = 1 if trade.direction in ('SELL','SHORT') else -1
            quantity = trade.quantity * direction
            trade.fake_exit_trade(self.market.updated_at, quantity * self.market.last_price(trade.symbol))

            self.all_trades.append(trade)

    def verify_portfolio_consistency(self):
        """ Checks for problematic values in current holding and position """

        if (self.holdings['cash'] < 0 or
            self.holdings['total'] < 0 or
            self.holdings['commission'] < 0):
            logging.critical('Cash, total or commission is negative. This shouldn\'t be possible.')
            logging.critical('Cash={}, Total={}, Commission={}'.format(
                self.holdings['cash'],
                self.holdings['total'],
                self.holdings['commission'],
            ))
            raise AssertionError("Inconsistency in Portfolio.holdings()")

        open_long = len(self.long_positions)
        open_short = len(self.short_positions)

        if open_long > self.MAX_LONG_POSITIONS or open_short > self.MAX_SHORT_POSITIONS:
            raise AssertionError("Number of open positions is too high. {}/{} open positions and {}/{} short positions".format(
                open_long,
                self.MAX_LONG_POSITIONS,
                open_short,
                self.MAX_SHORT_POSITIONS,
            ))

    def construct_holding(self, cur_datetime, cash, commission, total):
        """
        Holdings at a point in time. All properties represented in cash.
        Parameters:
            cur_datetime -- date of the point in time in question
            cash -- cash held
            commission -- cummulative commission paid up to this day
            total -- cash equivalent of all holdings combined - commission paid
        """
        if not isinstance(cur_datetime, datetime.datetime):
            raise TypeError("Improprer parameter type on portfolio.construct_holding()")

        holding = {}

        holding['datetime'] = cur_datetime
        holding['cash'] = cash
        holding['commission'] = commission
        holding['total'] = total

        return holding
