from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import sys
sys.path.append('E:\pyQuant\hyzou')
import backtrader as bt


import pandas as pd
import pymssql as ms
import datetime
from hyzou.BackTest.Strategy import First

class PandasDataOkCoin(bt.feeds.PandasData):

    params = (
        ('datetime',None),
        ('open', -1),
        ('high', -1),
        ('low', -1),
        ('close', -1),
        ('volume', -1),
        ('openinterest', -1),
    )

    #datafields = (['openprice', 'highprice', 'lowprice', 'closeprice', 'volume'])


def getData():
    conn=ms.connect(host="192.168.1.5", user="sa", password="Y2iaciej",
                                           database="Quant2")
    df=pd.read_sql('select timestamps as datetime,openprice as [open],highprice as [high],lowprice as low,closeprice as [close],volume,0 as openinterest from Kline',con=conn)

    return df

if __name__ == '__main__':
    cerebro = bt.Cerebro()



    cerebro.broker.setcash(100000.0)


    df=getData()

    df['datetime'] = df['datetime'].apply(lambda x:datetime.datetime.fromtimestamp(float(x)/1000))
    df=df.set_index(keys=['datetime'])
    df2=df.index[-1]
    data=PandasDataOkCoin(dataname=df,)

    cerebro.resampledata(data,timeframe=bt.TimeFrame.Minutes,compression=30)

    cerebro.addstrategy(First.TestStrategy)



    #cerebro.addanalyzer(Ana.SharpeRatio)
    #cerebro.addanalyzer(Ana.AnnualReturn)
    #cerebro.addanalyzer(Ana.SQN)

    print('Starting Portfolio Value: %.2f' % cerebro.broker.getvalue())

    cerebro.run()

    cerebro.plot()

    print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())