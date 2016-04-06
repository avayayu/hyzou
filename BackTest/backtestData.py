import logging

from common.data import MarketData, Bars
from common.events import MarketEvent

class BacktestMarketData(MarketData):

    def __init__(self, symbol_list=['bitcoin'], date_from='', date_to='',data_source='home',resample=None):

        super(BacktestMarketData, self).__init__(symbol_list,data_source=data_source)

        self.date_from = self._data[self.symbol_list[0]]['df'].index[0]
        self.date_to = self._data[self.symbol_list[0]]['df'].index[-1]

        self.is_market_opened=False

        for s in symbol_list:
            # Limit between date_From and date_to
            self._data[s]['df'] = self._data[s]['df'][date_from:] if date_from else self._data[s]['df']
            self._data[s]['df'] = self._data[s]['df'][:date_to] if date_to else self._data[s]['df']


            if resample is not None:
                try:
                    self._data[s]['df']=self._data[s]['df'].resample(resample)
                except Exception:
                    print('resample error')
                    return

            # Check for empty dfs
            if self._data[s]['df'].empty:
                logging.warning("Empty DataFrame loaded for {}.".format(s)) # Possibly invalid date ranges?

            # Dataframe iterrows  generator
            self._data[s]['bars'] = self._data[s]['df'].iterrows()

            # List that will hold all rows from iterrows, one at a time
            self._data[s]['latest_bars'] = []

        self.continue_execution = True

    def _update_bars(self):
        """
        Generator that updates all prices based on historical data and raises
        MarketEvents to simulate live trading. The order of events is:
            before_open - single event
            open - one event per symbol
            during - two events per symbol (low and high, depending if positive
                     negative day)
            close - one event per symbol
            after_close - single event

        Before raising MarketEvents, all prices need to be updated to maintain
        consistency otherwise portfolio_value will be calculated based on open price
        and it will influence position size calculation
        """

        try:
            # Before day starts, adding bars from yesterday to 'latest_bars'
            for s in self.symbol_list:
                if 'updated_at' in self._data[s]:
                    self._data[s]['latest_bars'].append(self._todays_bar(s))

            for s in self.symbol_list:
                new_row = next(self._data[s]['bars'])

                self._data[s]['updated_at'] = new_row[0]
                self._data[s]['open'] = new_row[1][0]
                self._data[s]['high'] = new_row[1][1]
                self._data[s]['low'] = new_row[1][2]
                self._data[s]['close'] = new_row[1][3]
                self._data[s]['volume'] = new_row[1][4]

            self.updated_at = new_row[0]

            #if self.is_market_opened==False:
                # Before open
            self._relay_market_event(MarketEvent('before_open',market_time=new_row[0]))
            yield

            # On open - open = latest_bars[-1][1]
            for s in self.symbol_list:
                self._data[s]['last_price'] = self._data[s]['open']
            for s in self.symbol_list:
                self._relay_market_event(MarketEvent('on_open',market_time=new_row[0],symbol=s))
                yield

            # During #1
            for s in self.symbol_list:
                d = self._data[s]
                self._data[s]['last_price'] = d['low'] if d['close']>d['open'] else d['high']
            for s in self.symbol_list:
                self._relay_market_event(MarketEvent('during',market_time=new_row[0],symbol=s))
                yield

            # During #2
            for s in self.symbol_list:
                d = self._data[s]
                self._data[s]['last_price'] = d['high'] if d['close']>d['open'] else d['low']
            for s in self.symbol_list:
                self._relay_market_event(MarketEvent('during',market_time=new_row[0],symbol=s))
                yield

            # On close
            for s in self.symbol_list:
                self._data[s]['last_price'] = self._data[s]['close']
            for s in self.symbol_list:
                self._relay_market_event(MarketEvent('on_close',market_time=new_row[0],symbol=s))
                yield

            # After close, last_price will still be close
            #if self.is_market_opened == False:
            self._relay_market_event(MarketEvent('after_close',market_time=new_row[0]))
            yield

        except StopIteration:
            self.continue_execution = False

if __name__=='__main__':
    data=BacktestMarketData()
    for s in data._update_bars():
        print(s)
