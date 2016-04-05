import BackTest as bt
from BackTest.Strategy import moving_average

st=moving_average.MovingAverage()
engine=bt.BacktestEngine(start_automatically=False,strategies=[st,],data_source='work')


engine.start()
engine.calc_performance()
engine.plot_results()

engine.print_all_trades()