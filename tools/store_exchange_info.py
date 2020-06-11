from binance.websockets import BinanceSocketManager
from binance.client import Client 
from pprint import pprint
import json

from ws_bb.config import *


client = Client(api_key=BINANCE_PUBLIC, api_secret=BINANCE_SECRET)
trading_info = client.get_exchange_info()

symbol_info = {}
for symbol_data in trading_info["symbols"]:
	step_size = symbol_data['filters'][2]['stepSize'].rstrip("0")
	symbol_info[symbol_data["symbol"]] = {"quote": symbol_data["quoteAsset"], 
										  "base": symbol_data["baseAsset"],
										  "decimals": step_size.count("0")
										 }
relavant = dict([(symbol, data) for symbol, data in symbol_info.items() if symbol in SUPPORTED_MARKETS])


with open("./ws_bb/data/exchange_info.json", "w") as exchange_info_file:
	json.dump(relavant, exchange_info_file)


