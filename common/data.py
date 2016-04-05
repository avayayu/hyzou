import logging

import pandas as pd
import pymssql as ms
import numpy as np
from common.events import *
import datetime

class Bars(object):
    """
    Object exposed to users to reflect prices on a single or on multiple days.
    """
    def __init__(self, latest_bars, single_bar=False):
        self.length = len(latest_bars)

        if single_bar:
            self.datetime = latest_bars[-1][0]
            self.open = latest_bars[-1][1]
            self.high = latest_bars[-1][2]
            self.low = latest_bars[-1][3]
            self.close = latest_bars[-1][4]
            self.volume = latest_bars[-1][5]
            self.is_positive = True if self.close > self.open else False
        else:
            self.datetime = [i[0] for i in latest_bars]
            self.open = [i[1] for i in latest_bars]
            self.high = [i[2] for i in latest_bars]
            self.low = [i[3] for i in latest_bars]
            self.close = [i[4] for i in latest_bars]
            self.volume = [i[5] for i in latest_bars]

    def mavg(self, price_type='close'):
        return np.mean(getattr(self, price_type))


    def __len__(self):
        return self.length

    def __str__(self):
        return str(self.datetime)+' open:'+str(self.open) + ' high:'+str(self.high)+' low:'+str(self.low)+' close:'+str(self.close)+' volume:'+str(self.volume)


class BarError(Exception):
    """ Required for a specific type of Error that is catched on portfolio. """
    pass


class MarketData(object):
    def __init__(self,symbol_list=['bitcoin'],data_source='home'):
        start_load_time=datetime.datetime.now()

        self.symbol_list=symbol_list

        self.data_source=data_source

        self._data={}

        self._last_historical_bar_for = {}
        for symbol in symbol_list:
            self._data[symbol] = {}
            df=self.loadData(symbol=symbol)
            self._data[symbol]['df']=df
            self._last_historical_bar_for[symbol]=self._data[symbol]['df'].index[-1]

        self._pad_empty_values()

        self.load_time = datetime.datetime.now()-start_load_time

        print('load data took '+str(self.load_time.seconds) + " secs")

        self.events_queue_list = []

        self.market_events_list=[]




    def dbConnection(self,dbname):
        if(dbname=='work'):
            con=ms.connect(host="10.31.201.123", user="sa", password="Y2iaciej",
                                           database="IBdata")
            return con
        if(dbname=='home'):
            con=ms.connect(host="192.168.1.5", user="sa", password="Y2iaciej",
                                           database="Quant2")
            return con

    def loadData(self,symbol,):
        if(symbol=='bitcoin'):
            con=self.dbConnection(self.data_source)
            df=pd.read_sql('select [timestamps] as [datetime],openprice as [open],highprice as [high],lowprice as [low],closeprice as [close], volume from kline order by timestamps asc',con)
            df['datetime']=df['datetime'].apply(lambda x:datetime.datetime.fromtimestamp(float(x)/1000))
            df=df.set_index(keys=['datetime'])
            return df

    def _pad_empty_values(self):
        for s in self.symbol_list:
            df = self._data[s]['df']

            # Fill NaN with 0 in volume column
            df['volume'] = df['volume'].fillna(0)
            # Pad close price forward
            df['close'] = df['close'].ffill()
            # Fill any remaining close NaN in 0 (e.g. beginning of file)
            df['close'] = df['close'].fillna(0)

            # Fill open high and low NaN with close price
            for col in ['open', 'high', 'low']:
                df[col] = df[col].fillna(df['close'])

            self._data[s]['df'] = df

    def _relay_market_event(self, e):
        """ Puts e, which should be a MarketEvent on all queues in self.events_queue_list """

        if isinstance(e, MarketEvent):
            [q.put(e) for q in self.events_queue_list]
            self.market_events_list.append(e)
        else:
            raise TypeError("MarketData._relay_market_event only accepts MarketEvent objects.")

    def _update_based_on_external_data(self, market_event):
        """ Takes data provided by a broker and updates internal registries. Not used for backtesting,
        as self updates them based on CSV files and not a broker. """
        pass
    def _todays_bar(self, symbol):
        """ Returns today's prices, volume and last_timestamp as an ordered tuple. """
        return (
            self._data[symbol]['updated_at'],
            self._data[symbol]['open'],
            self._data[symbol]['high'],
            self._data[symbol]['low'],
            self._data[symbol]['close'],
            self._data[symbol]['volume'],
        )

    def last_price(self, symbol):
        """ Returns last recorded price """
        if not 'last_price' in self._data[symbol]:
            raise BarError("No price recorded for {} today".format(symbol))
        return self._data[symbol]['last_price']

    def high(self, symbol):
        if not 'high' in self._data[symbol]:
            raise BarError("No high recorded for {}".format(symbol))
        return self._data[symbol]['high']

    def low(self, symbol):
        if not 'low' in self._data[symbol]:
            raise BarError("No low recorded for {}".format(symbol))
        return self._data[symbol]['low']

    def volume(self, symbol):
        if not 'volume' in self._data[symbol]:
            raise BarError("No volume recorded for {}".format(symbol))
        return self._data[symbol]['volume']

    # def change(self, symbol):
    #     """ Returns change between last close and last recorded price """
    #     # In case execution just started and there is no current price
    #     if not 'last_price' in self._data[symbol]:
    #         raise BarError("No price recorded for {} today".format(symbol))
    #     last_close = self.yesterday(symbol).close
    #     return self._data[symbol]['last_price']/last_close - 1



    def bars(self, symbol, N=1):
        """ Returns latest N bars including today's values """
        return self._bar_dispatcher('bars', symbol, N)

    def past_bars(self, symbol, N=1):
        """ Returns latest N bars not including today's values """
        return self._bar_dispatcher('past_bars', symbol, N)

    def today(self, symbol):
        """ Returns today's OHLC values in a bar """
        return self._bar_dispatcher('today', symbol)

    def yesterday(self, symbol):
        """ Returns yesterday's values - last bar in self._latest_bars """
        return self._bar_dispatcher('yesterday', symbol)

    def _bar_dispatcher(self, option, symbol, N=1, ):
        if option == 'today':
            bars = [self._todays_bar(symbol)]

        elif option == 'yesterday':
            bars = self._data[symbol]['latest_bars'][-1:]

        elif option == 'bars':
            bars = self._data[symbol]['latest_bars'][-(N-1):]
            bars.append(self._todays_bar(symbol))

        elif option == 'past_bars':
            bars = self._data[symbol]['latest_bars'][-N:]

        if not bars:
            raise BarError("Something wrong with latest_bars")

        if len(bars) != N:
            raise BarError("Not enough bars yet.")

        if len([bar for bar in bars if bar[4] > 0.0]) != len(bars):
            raise BarError("Empty bars found. Latest_bars for {} has one or more 0.0 close prices, and will be disconsidered.".format(symbol))

        result = Bars(bars, True) if option in ('today', 'yesterday') else Bars(bars)
        return result


def _is_dataframe_good(symbol, df):
    if (df['high'] < df['open']).any() == True:
        dates = df.loc[(df['high'] < df['open']) == True].index.format()
        logging.warning('Inconsistent data detected - {} high < open on {}'.format(symbol, dates))
        return False

    if (df['high'] < df['close']).any() == True:
        dates = df.loc[(df['high'] < df['close']) == True].index.format()
        logging.warning('Inconsistent data detected - {} high < close on {}'.format(symbol, dates))
        return False
    if (df['low'] > df['open']).any() == True:
        dates = df.loc[(df['low'] > df['open']) == True].index.format()
        logging.warning('Inconsistent data detected - {} low > open on {}'.format(symbol, dates))
        return False

    if (df['low'] > df['close']).any() == True:
        dates = df.loc[(df['low'] > df['close']) == True].index.format()
        logging.warning('Inconsistent data detected - {} low > close on {}'.format(symbol, dates))
        return False

    if (df['high'] < df['low']).any() == True:
        dates = df.loc[(df['high'] < df['low']) == True].index.format()
        logging.warning('Inconsistent data detected - {} high < low on {}'.format(symbol, dates))
        return False

    return True