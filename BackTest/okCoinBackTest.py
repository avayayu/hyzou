from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import backtrader as bt
from backtrader import strategy
import backtrader.analyzers as Ana
if __name__ == '__main__':
    cerebro = bt.Cerebro()

    print('Starting Portfolio Value: %.2f' % cerebro.broker.getvalue())

    cerebro.run()

    cerebro.plot()

    cerebro.addanalyzer(Ana.SharpeRatio)
    cerebro.addanalyzer(Ana.AnnualReturn)
    cerebro.addanalyzer(Ana.SQN)

    print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())