from binance.client import Client
import itertools as it
from pprint import pprint
import json

import helpers as hp
from config import *


NORMALIZING_ASSET = "BTC"
NORMALIZED_START_AMOUNT = 0.0015
HEADER = {
        "instance_id": "Bot 1",
        "global_settings": {"fees": {"BINANCE": "0.00075"}},
        "plans": []
	}
FEE_ASSET = "START_ASSET"
PROFIT_ASSET = "START_ASSET"


def format_exchange_info(exchange_info_raw_):
	exchange_info = {}
	for symbol_data in exchange_info_raw_["symbols"]:
		step_size = symbol_data['filters'][2]['stepSize'].rstrip("0")
		exchange_info[symbol_data["symbol"]] = {"quote": symbol_data["quoteAsset"], 
											  "base": symbol_data["baseAsset"],
											  "decimals": step_size.count("0")
											 }
	relavant = dict([(symbol, data) for symbol, data in exchange_info.items() if symbol in SUPPORTED_MARKETS])

	return relavant


client = Client(api_key=BINANCE_PUBLIC, api_secret=BINANCE_SECRET)
prices_raw = client.get_all_tickers()
prices_dict = dict([(market["symbol"], market["price"]) for market in prices_raw])
exchange_info_raw = client.get_exchange_info()
exchange_info = format_exchange_info(exchange_info_raw)
paths_all = it.permutations(SUPPORTED_MARKETS, 3)

plans = []
for plan_no, path in enumerate(paths_all):
	actions = []
	for i in range(len(path)):
		next_index = 0 if i == len(path)-1 else i + 1
		quote = exchange_info[path[i]]["quote"]
		base = exchange_info[path[i]]["base"]
		cond1 =  quote in path[next_index] and quote not in path[i-1]
		cond2 = base in path[next_index] and base not in path[i-1]
		if not (cond1 or cond2):
			break
		actions.append({"symbol": path[i], 
						"quote": quote, 
						"base": base, 
						"decimals": exchange_info[path[i]]["decimals"], 
						"exchange": "BINANCE"})
	else:
		start_asset = actions[0]["base"] if actions[0]["base"] in actions[-1]["symbol"] else actions[0]["quote"]
		
		# Finding the right symbol for base and holding asset
		if start_asset == NORMALIZING_ASSET:
			price = 1
		elif start_asset + NORMALIZING_ASSET in prices_dict:
			price = 1 / float(prices_dict[start_asset + NORMALIZING_ASSET])
		elif NORMALIZING_ASSET + start_asset in prices_dict:
			price = float(prices_dict[NORMALIZING_ASSET + start_asset])
		else:
			raise Exception(f"Combination of {start_asset} and {NORMALIZING_ASSET} not listed.")
			
		start_amount = round(NORMALIZED_START_AMOUNT * price, 5)
		plan = {"markets": actions, 
				"start_currency": start_asset, 
				"start_amount": str(start_amount),
				"fee_asset": start_asset if FEE_ASSET == "START_ASSET" else FEE_ASSET,
				"profit_asset": start_asset if PROFIT_ASSET == "START_ASSET" else PROFIT_ASSET, 
				"strategy": "ARBITRAGE", 
				"plan_no": plan_no}
		plans.append(plan)


deployment_settings = HEADER
deployment_settings["plans"] = plans
with open("./data/deploymentSettings.json", "w") as ds_file:
	json.dump(deployment_settings, ds_file, indent=4)

print(f"{len(plans)} valid paths.")