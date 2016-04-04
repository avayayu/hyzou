import hyzou.BackTest as bt
from hyzou.BackTest.Strategy import moving_average

st=moving_average.MovingAverage()
engine=bt.BacktestEngine(start_automatically=False,strategies=[st,])


engine.start()