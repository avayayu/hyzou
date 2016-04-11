import logging

from common.data import MarketData, Bars
from common.events import MarketEvent
from okCoin import OkcoinSpotAPI as okCoin
import sys,time
import pandas as pd
import datetime

class okCoinLivingMarketData(MarketData):

    def __init__(self,resample='60t'):
        self.apikey = '32889f87-6c37-4d17-a1ed-e067c046498b'
        self.secretkey = 'CA947B770C9D6D87E1C87B1B8AF7A1B4'
        self.okcoinRESTURL = 'www.okcoin.cn'   #请求注意：国内账号需要 修改为 www.okcoin.cn
        self.okcoinSpot = okCoin.OKCoinSpot(self.okcoinRESTURL,self.apikey,self.secretkey)
        self.df_raw=None
        self.df_resample=None
        self.resample=resample
        self.now_date=None


    def _update_based_on_external_data(self, market_event):
        pass


    def _update_bars(self):
        now=self.okcoinSpot.ticker(symbol='symbol')
        date=now['date']
        ticker=now['ticker']
        self.now_date=date

        self._data['bitcoin']['updated_at'] = date
        self._data['bitcoin']['close'] = ticker['now']
        self._relay_market_event(MarketEvent('during',market_time=datetime.datetime.fromtimestamp(float(self.now_date)/1000),symbol='bitcoin'))
        yield

    def past_bars(self, symbol, N=1):
        jsonResult=self.okcoinSpot.getKLine(symbol='btc_cny',since=(self.now_date-7*24*60*60*100),type='1min',size=7*24*60)
        self.df_raw=pd.DataFrame(jsonResult,columns=['timestamps','openprice','highprice','lowprice','closeprice','volume'])
        self.df_resample=self.df_raw.resample(self.resample)
        return self.df_resample.iloc[-N:0]

    def bars(self, symbol, N=1):
        """ Returns latest N bars including today's values """
        return self._data['bitcoin']['close']


if __name__=='__main__':
    data=okCoinLivingMarketData()
    while True:
        time.sleep(0.2)
        print(data._update_bars())