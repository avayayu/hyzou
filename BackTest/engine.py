from datetime import timedelta, datetime
import logging

import matplotlib.pyplot as plt
import pandas as pd


#from hyzou import settings
from BackTest import backtestData
from common.strategy import Strategy
from BackTest.backtestPortfolio import BacktestPortfolio


class BacktestEngine(object):
    def __init__(self, strategies,symbol_list=['bitcoin'], start_automatically=True,data_source='home',resample=None):

        if not strategies:
            raise ValueError("Empty strategies list in your algo file.")

        self.symbol_list=symbol_list

        # Single market object will be used for all backtesting instances
        self.market = backtestData.BacktestMarketData(symbol_list=self.symbol_list,data_source=data_source,resample=resample)

        self.resample=resample

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

    def plot_all(self):
        for portfolio in self.portfolios:
            returnSeries = portfolio.performance['equity_curve']
            #positionSeries=portfolio.performance['positions']
            returnSeries=returnSeries.resample(self.resample,fill_method='bfill')

            fig = plt.figure()

            ax0 = plt.subplot(221)
            ax1 = plt.subplot(222)
            ax2 = plt.subplot(212)

            ax0.plot(returnSeries)
            ax0.set_title('Accumulative Return Curve')
            ax0.set_xlabel('time')
            ax0.set_ylabel('netValue')

            return_all=portfolio.performance['return']

            n, bins, patches = ax1.hist(return_all, 50, normed=1, facecolor='green', alpha=0.5)
            ax1.set_xlabel('return')
            ax1.set_ylabel('frequency')

            ax1.set_title(r'Histogram of Each Trade Absolute Return')

            columns = ['total_return', 'ann_return', 'sharpe', 'pct_trades_profit', 'pct_trades_loss', 'maxdrawn',
                       'trades']
            rows = ['value']
            statistic = []

            statistic.append(str('%1.2f%%' % portfolio.performance['total_return']))
            statistic.append(str('%1.2f%%' % portfolio.performance['ann_return']))
            statistic.append(str('%1.2f' % portfolio.performance['sharpe']))
            statistic.append(str('%1.2f %%' % portfolio.performance['pct_trades_profit']))
            statistic.append(str('%1.2f %%' % portfolio.performance['pct_trades_loss']))
            statistic.append(str('%1.2f %%' % portfolio.performance['dd_max']))
            statistic.append(str('%1.1f' % portfolio.performance['trades']))

            nrows=1
            ncols=len(statistic)

            hcell,wcell=0.3,1
            hpad,wpad=0,0

            ax2.xaxis.set_visible(False)
            ax2.yaxis.set_visible(False)

            for sp in ax2.spines.values():
                sp.set_color('w')
                sp.set_zorder(0)

            the_table = ax2.table(cellText=[statistic],
                              rowLabels=rows,
                              colLabels=columns,
                              loc='center')
            the_table.auto_set_font_size(False)
            table_props = the_table.properties()
            table_cells = table_props['child_artists']
            for cell in table_cells:
                cell.set_width(0.1)
                cell.set_height(0.065)
                cell.set_fontsize(14)



            the_table.set_zorder(10)

            figManager = plt.get_current_fig_manager()
            figManager.window.showMaximized()


            plt.tight_layout()
            plt.show()

