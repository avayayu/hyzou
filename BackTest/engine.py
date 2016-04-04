from datetime import timedelta, datetime
import logging

import matplotlib.pyplot as plt
import pandas as pd


#from hyzou import settings
from hyzou.BackTest import backtestData
from hyzou.common.strategy import Strategy
from hyzou.BackTest.backtestPortfolio import BacktestPortfolio


class BacktestEngine(object):
    def __init__(self, strategies,symbol_list=['bitcoin'], start_automatically=True):

        if not strategies:
            raise ValueError("Empty strategies list in your algo file.")
        self.symbol_list=symbol_list
        # Single market object will be used for all backtesting instances
        self.market = backtestData.BacktestMarketData(symbol_list=self.symbol_list)

        self.portfolios = []

        for strategy in strategies:
            port = BacktestPortfolio(self.market, strategy)
            self.portfolios.append(port)

        logging.info("Backtesting {} {} with {} symbols from {} to {}".format(
            len(self.portfolios),
            'strategies' if len(self.portfolios) > 1 else 'strategy',
            len(self.market.symbol_list),
            self.market.date_from.strftime('%Y-%m-%d'),
            self.market.date_to.strftime('%Y-%m-%d'),
        ))
        logging.info("Data load took {}".format(str(self.market.load_time)))

        if start_automatically:
            self.start()
            self.calc_performance()

    def start(self):
        """
        Starts backtesting for all portfolios created.
        New market events are handled on this level to allow for multiple portfolios
        to run simultaneously with a single market object
        """
        start_time = datetime.now()
        while self.market.continue_execution:
            for _ in self.market._update_bars():
                [portfolio.run_cycle() for portfolio in self.portfolios]

        [portfolio.update_last_holdings() for portfolio in self.portfolios]

        logging.info("Backtest took " + str((datetime.now()-start_time)))

    def calc_performance(self, order_by='sharpe'):
        start_time = datetime.now()

        [portfolio.calc_performance() for portfolio in self.portfolios]

        # Order engines by sharpe (used for plotting)
        self.portfolios = sorted(self.portfolios, key=lambda x: x.performance[order_by], reverse=True)

        # Calc results dataframe that contains performance for all portfolios
        self.results = pd.DataFrame(
            [[
                str(portfolio.strategy),
                portfolio.performance['total_return'],
                portfolio.performance['ann_return'],
                portfolio.performance['sharpe'],
                portfolio.performance['trades'],
                portfolio.performance['pct_trades_profit'],
                portfolio.performance['dangerous'],
                portfolio.performance['dd_max'],
            ] for portfolio in self.portfolios ],
            columns=[
                'strategy',
                'total returns',
                'annualised return',
                'sharpe',
                '# trades',
                'profit %',
                'dangerous',
                'max dd',
            ],
        )

        logging.debug("Performance calculated in {}".format(str(datetime.now()-start_time)))

    def plot_open_positions(self):
        for portfolio in self.portfolios:
            ax = portfolio.performance['all_positions']['open_trades'].plot()
            ax.set_title(portfolio.strategy)
            plt.grid()
            plt.show()

    def plot_results(self):
        for portfolio in self.portfolios:
            ax = portfolio.performance['equity_curve'].plot()
            ax.set_title(portfolio.strategy)
            plt.grid()
            plt.show()

    def plot_symbol_subscriptions(self):
        for portfolio in self.portfolios:
            portfolio.performance['subscribed_symbols'].plot()
            plt.show()

    def print_all_trades(self):
        for port in self.portfolios:
            print(port.performance['all_trades'])

    def strategy_finishing_methods(self):
        [portfolio.strategy.after_backtest(portfolio.performance) for portfolio in self.portfolios]
