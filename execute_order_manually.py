from binance.client import Client, BinanceAPIException
import concurrent.futures
import itertools as it
from pprint import pprint
import json
import time

import helpers as hp
from config import *


client = Client(api_key=BINANCE_PUBLIC, api_secret=BINANCE_SECRET)

with concurrent.futures.ThreadPoolExecutor() as executor:
    threads = []
    for _ in range(2):
        thread = executor.submit(client.create_order,
                                 symbol="ETHUSDT",
                                 side="SELL",
                                 type="MARKET",
                                 quantity=0.05
                                 )
        threads.append(thread)

responses = []
failed_responses = []
for thread in threads:
    try:
        response = thread.result()
    except BinanceAPIException as e:
        print(repr(e))
        print(e.status_code)
        print(e.message)
        print(e.code)
        print(e.response)
        print(e.request.body)
        print("What is going on!!!??")
        if e.code == -2010:
            print("Insufficient balance")
        else:
            raise e