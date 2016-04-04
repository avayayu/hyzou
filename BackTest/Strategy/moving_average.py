from  hyzou.common.strategy import  *
import hyzou.common.data as dt
class MovingAverage(Strategy):
    def initialize(self):
        self.SYMBOL_LIST=['bitcoin']
        self.fast = self.get_arg(0, 5)
        self.slow = self.get_arg(1, 15)

    def during(self, symbol):
        print(self.market._todays_bar(symbol=symbol))

    def after_close(self):
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


# strategies = [MovingAverage(5,i) for i in botcoin.optimize((5,100,5))]
