from  common.strategy import  *
import common.data as dt
import pandas as pd


class MovingAverage(Strategy):

    def initialize(self):

        self.SYMBOL_LIST=['bitcoin']
        self.fast = self.get_arg(0, 5)
        self.slow = self.get_arg(1, 15)



    def on_close(self,symbol,event=None):
        for symbol in self.SYMBOL_LIST:
            try:
                slow = self.market.bars(symbol, self.slow).mavg('close')
                fast = self.market.bars(symbol, self.fast).mavg('close')

                if fast > slow:
                    self.buy(symbol)
                if fast < slow:
                    self.sell(symbol)
            except dt.BarError as e:
                pass
    #def on_open(self,symbol,event=None):
        #list=self.market.bars(symbol=symbol,N=20)
        #print('today is ' + str(event.market_time) + '  ' + str(self.market.yesterday(symbol=symbol)))




# strategies = [MovingAverage(5,i) for i in botcoin.optimize((5,100,5))]
