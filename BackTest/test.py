import BackTest as bt
from BackTest.Strategy import moving_average,taLib_strategy
import sys
print(sys.path)
st=moving_average.MovingAverage()
st2=taLib_strategy.STOCHRSIStrategy()
engine=bt.BacktestEngine(start_automatically=False,strategies=[st2,],data_source='work',resample='60t')


engine.start()
engine.calc_performance()
engine.plot_all()

engine.print_all_trades()