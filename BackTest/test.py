import BackTest as bt
from BackTest.Strategy import moving_average
import sys
print(sys.path)
st=moving_average.MovingAverage()
engine=bt.BacktestEngine(start_automatically=False,strategies=[st,],data_source='work',resample='60t')


engine.start()
engine.calc_performance()
engine.plot_all()

engine.print_all_trades()