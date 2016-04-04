import logging
import queue
from hyzou.common.trade import *
from hyzou.common.events import *
from hyzou.common.data import BarError
import pandas as pd
import numpy as np
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
        self.strategy.events_queue = self.events_queue
        self.strategy.market = self.market
        self.strategy.risk = self.risk
        #self.risk = RiskAnalysis(self.strategy.settings, self.cash_balance, self.net_liquidation)
        self.market.events_queue_list.append(self.events_queue)
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
    def generate_orders(self, signal):
        symbol = signal.symbol
        direction = signal.direction
        date = self.market.updated_at

        # Checks for common consistency errors in signals (usually sign of a broken strategy)
        self.check_signal_consistency(symbol, signal.price, direction)

        # Adjusts execution price for slippage
        execution_price = self.risk.adjust_price_for_slippage(direction, signal.price)

        cur_quantity = self.open_trades[symbol].entry_filled_quantity if symbol in self.open_trades else 0
        quantity = 0

        if direction in ('BUY', 'SHORT') and cur_quantity == 0:

            if ((len(self.long_positions) < self.MAX_LONG_POSITIONS and direction == 'BUY') or
                (len(self.short_positions) < self.MAX_SHORT_POSITIONS and direction == 'SHORT')):

                quantity, estimated_commission = self.risk.calculate_quantity_and_commission(direction, execution_price)

        elif direction in ('SELL', 'COVER') and cur_quantity != 0:
            quantity, estimated_commission = self.risk.calculate_quantity_and_commission(direction, execution_price, cur_quantity)

        # Checking if quantity is consistent to direction
        if (quantity < 0 and direction in ('BUY','COVER')) or (quantity > 0 and direction in ('SHORT','SELL')):
            logging.warning(
                "{} {} order quantity for {}. Cash balance {}, price {}, round lot size {}. This is a sign of inconsistency in portfolio holdings.".format(
                quantity, direction, self.strategy, self.cash_balance(), execution_price, self.ROUND_LOT_SIZE,
            ))
            return

        if quantity != 0:
            order = OrderEvent(symbol, direction, quantity, execution_price, self.get_next_order_id())

            self.events_queue.put(order)

    def check_signal_consistency(self, symbol, signal_price, direction):
        """
        Looks for consistency errors common during backtesting and live trading,
        such as execution price much different than current price, outside low-high range,
        or negative price, etc.
        """
        if signal_price <= 0:
            raise ValueError("Can't execute Signal with negative price. Strategy {}, date {}, symbol {}, price {}.".format(
                self.strategy, self.market.updated_at, symbol, signal_price
            ))

    def execute_order(self, order):
        if order.direction in ('BUY', 'SHORT'):
            # entered_at = self.market.updated_at if self.is_backtesting else datetime.datetime.now()
            trade = Trade(order.symbol, order.direction, order.quantity, order.limit_price, self.market.updated_at, order)
            # add reference to trade in portfolio's open_trades dict
            self.open_trades[order.symbol] = trade
        else:
            # Checks if there is a similar order in pending_orders to protect
            # against repeated signals coming from strategy
            if self.open_trades[order.symbol].exit_order:
                logging.critical("Possible duplicate order being created in portfolio.")

            # Flags trade as exiting by adding the pending exit order to it
            self.open_trades[order.symbol].update_exit_order(order)

    def archive_trade_if_exited(self, fill):
        # remove trade from open_trades if it has been exited
        if self.open_trades[fill.symbol].exit_is_fully_filled:
            self.all_trades.append(self.open_trades[fill.symbol])
            del self.open_trades[fill.symbol]

    def status_reporting(self):
        from hyzou.LiveTrading.utils import _round
        logging.debug("Portfolio reporting - cash balance {} - net liquidation {}".format(self.cash_balance(), self.net_liquidation()))
        for s,t in self.open_trades.items():
            try:
                price = self.market.last_price(s)
            except BarError:
                price = 0.0

            logging.debug("Trade {} {} {} - unrealized pnl {} - entry/current price {}/{}".format(
                t.direction, t.quantity, s, t.unrealized_pnl, _round(t.entry_avg_cost), price
            ))

    def calc_performance(self):
        """
        Calculates multiple performance stats given a portfolio object.
        """
        def drawdown(curve):
            hwm = [0]
            eq_idx = curve.index
            drawdown = pd.Series(index = eq_idx)
            duration = pd.Series(index = eq_idx)

            # Loop over the index range
            for t in range(1, len(eq_idx)):
                cur_hwm = max(hwm[t-1], curve[t])
                hwm.append(cur_hwm)
                drawdown[t]= (hwm[t] - curve[t])/hwm[t]
                duration[t]= 0 if drawdown[t] == 0 else duration[t-1] + 1

            return drawdown.max()*100, duration.max()

        if not self.all_holdings:
            raise ValueError("Portfolio with empty holdings")
        results = {}

        # Saving all trades
        results['all_trades'] = pd.DataFrame(
            [(
                t.symbol,
                t.pnl,
                t.entered_at,
                t.exited_at,
                t.quantity,
                t.entry_avg_cost,
                t.exit_avg_cost,
                t.entry_commission + t.exit_commission,
            ) for t in self.all_trades],
            columns=['symbol', 'pnl', 'entered_at', 'exited_at',
                     'quantity', 'open_price', 'close_price', 'commission'],
        )

        results['dangerous_trades'] = results['all_trades'][
            results['all_trades']['pnl'] >
            sum(results['all_trades']['pnl'])*self.THRESHOLD_DANGEROUS_TRADE
        ]

        # Saving portfolio.all_holdings in performance
        curve = pd.DataFrame(self.all_holdings)
        curve.set_index('datetime', inplace=True)
        results['all_holdings'] = curve

        # Creating equity curve
        curve['returns'] = curve['total'].pct_change()
        curve['equity_curve'] = (1.0+curve['returns']).cumprod()
        results['equity_curve'] = curve['equity_curve']

        # Number of days elapsed between first and last bar
        days = (curve.index[-1]-curve.index[0]).days
        years = days/365.2425

        # Average bars each year, used to calculate sharpe ratio (N)
        avg_bars_per_year = len(curve.index)/years # curve.groupby(curve.index.year).count())

        # Total return
        results['total_return'] = ((curve['equity_curve'][-1] - 1.0) * 100.0)

        # Annualised return
        results['ann_return'] = results['total_return'] ** 1/years

        # Sharpe ratio
        results['sharpe'] = np.sqrt(avg_bars_per_year) * curve['returns'].mean() / curve['returns'].std() if curve['returns'].mean() else 0.0

        # Trades statistic
        results['trades'] = len(self.all_trades)
        results['trades_per_year'] = results['trades']/years
        results['pct_trades_profit'] = len([trade for trade in self.all_trades if trade.pnl > 0])/results['trades'] if results['trades'] else 0.0
        results['pct_trades_loss'] = len([trade for trade in self.all_trades if trade.pnl <= 0])/results['trades'] if results['trades'] else 0.0

        # Dangerous trades that constitute more than THRESHOLD_DANGEROUS_TRADE of returns
        results['dangerous'] = True if not results['dangerous_trades'].empty else False

        # Drawdown
        results['dd_max'], results['dd_duration'] = drawdown(results['equity_curve'])

        # Subscribed symbols
        results['subscribed_symbols'] = results['all_holdings']['subscribed_symbols']
        results['avg_subscribed_symbols'] = results['all_holdings']['subscribed_symbols'].mean()

        self.performance = results
        return results


    def update_from_fill(self, fill):
        raise NotImplemented("Portfolio needs to implement update_from_fill")

    def get_next_order_id(self):
        raise NotImplemented("Portfolio needs to implement get_next_order_id")