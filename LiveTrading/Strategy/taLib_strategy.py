import talib
from  common.strategy import  *
import common.data as dt
import pandas as pd
import numpy as np


class STOCHRSIStrategy (Strategy):
    def initialize(self):
        self.SYMBOL_LIST = ['bitcoin']
        self.close=[]
        #self.count=0

    def on_close(self, symbol,event=None):
        for sym in self.SYMBOL_LIST:
            try:
                bar = self.market.bars(sym)
                self.close.append(bar.close[0])

                if len(self.close)>=100:
                    fastk, fastd = talib.STOCHRSI(np.asarray(self.close), timeperiod=20, fastk_period=45, fastd_period=24, fastd_matype=0)
                    # if fastk > fastd:
                    #    self.buy(symbol)
                    # if fastk < fastd:
                    #    self.sell(symbol)
                    now=fastk[len(fastk)-1]
                    last=fastk[len(fastk)-2]
                    if now==100 or now>last:
                        self.buy(symbol)
                    if now==0 or now<last:
                        self.sell(symbol)

                    #print(fastk)
                    #print(str(len(fastk)))
            except dt.BarError as e:
                pass

    # def during(self, symbol,event=None):
    #     for sym in self.SYMBOL_LIST:
    #         try:
    #             slow = self.market.bars(symbol, self.slow).mavg('close')
    #             fast = self.market.bars(symbol, self.fast).mavg('close')
    #
    #             if fast > slow:
    #                 self.buy(symbol)
    #             if fast < slow:
    #                 self.sell(symbol)
    #         except dt.BarError as e:
    #             pass




