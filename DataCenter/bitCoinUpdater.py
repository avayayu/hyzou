import pymssql as ms
from okCoin import OkcoinSpotAPI
import pandas as pd
from datetime import *

from sqlalchemy import  *

# import DataCenter.myConnection as con
from sqlalchemy.ext.declarative import declarative_base

# def writeFrameToDB(frame,con,table_name):
#     base = declarative_base()
#
#     meta = MetaData()
#
#
#     engine = create_engine('mssql+pymssql://sa:Y2iaciej@10.31.201.123/IBData')
#
#     t = Table('Kline',meta,autoload_with=engine, autoload=True)
#
#     meta.


con=ms.connect(host="10.31.201.123", user="sa", password="Y2iaciej",
                                           database="IBData")

df=pd.read_sql('select max(timeStamps) as begindate from Kline',con=con)
begindate = str(int(df.begindate[0]))

apikey = '32889f87-6c37-4d17-a1ed-e067c046498b'
secretkey = 'CA947B770C9D6D87E1C87B1B8AF7A1B4'
okcoinRESTURL = 'www.okcoin.cn'   #请求注意：国内账号需要 修改为 www.okcoin.cn

timeArray = datetime.fromtimestamp(float(begindate)/1000)
now=datetime.now()
detal=now-timeArray
size=int(detal.total_seconds()/60)

#现货API
okcoinSpot = OkcoinSpotAPI.OKCoinSpot(okcoinRESTURL,apikey,secretkey)

jsonResult=okcoinSpot.getKLine(symbol='btc_cny',since=begindate,type='1min',size=size)
result=pd.DataFrame(jsonResult,columns=['timestamps','openprice','highprice','lowprice','closeprice','volume'])


engine = create_engine('mssql+pymssql://sa:Y2iaciej@10.31.201.123/IBData')
result.to_sql("KLine",engine,if_exists = 'append',index=None,chunksize=100)
print(okcoinSpot.userinfo())
print(jsonResult)


