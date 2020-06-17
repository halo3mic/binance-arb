# Multiple checks are skipped:
#   - Decimals are pulled straight from the API 
#   - Market bases and quotes are pulled straight from the API
#   - DeploymentFactory raises an error if market with proposed symbol doesn't exist
#   - ...


import json
import traceback
from pprint import pprint
from binance.client import Client

import helpers as hp
from config import *


VALID_STRATEGIES = ["TEST", "ARBITRAGE"]
VALID_EXCHANGES = ["BINANCE"]
AMOUNT_LIMIT_MIN = 10
AMOUNT_LIMIT_MAX = 50
VALID_NORMALIZATION_ASSET = "USDT"
VALID_GENERAL_KEYS = []
VALID_PLAN_KEYS = []


class ValidityChecker:

	def __init__(self, deployment_file_path):
		self.deployment_file_path = deployment_file_path
		self.prices = None
		self.relevant_symbol_info = None
		self.relevant_assets = None

	def gather_data(self):
		# Get the deployment file
		with open(self.deployment_file_path) as dfile:
			self.deployment_file = json.load(dfile)

		client = Client(api_key=BINANCE_PUBLIC, api_secret=BINANCE_SECRET)
		# Get the last prices	
		prices_raw = client.get_all_tickers()
		self.prices = dict([(market["symbol"], market["price"]) for market in prices_raw])
		# Get the trade-information
		symbols_info_raw = client.get_exchange_info()
		symbol_info = {}
		assets = set()
		for symbol_data in symbols_info_raw["symbols"]:
			if symbol_data["symbol"] not in SUPPORTED_MARKETS:
				continue  # Save only relevant data
			step_size = symbol_data['filters'][2]['stepSize'].rstrip("0")
			symbol_info[symbol_data["symbol"]] = {"quote": symbol_data["quoteAsset"], 
												  "base": symbol_data["baseAsset"],
												  "decimals": step_size.count("0")
												}
			assets.add(symbol_data["quoteAsset"])
			assets.add(symbol_data["baseAsset"])

		self.relevant_symbol_info = dict([(symbol, data) for symbol, data in symbol_info.items() if symbol in SUPPORTED_MARKETS])
		self.relevant_assets = assets

	@staticmethod
	def test_structure_dicts_datatypes(dict_datatype, target):
		# Test that keys in the plan are expected ones
		assert target.keys() == dict_datatype.keys()
		# Test that values in plan have expected data-type
		for key in dict_datatype:
			assert type(target[key]) == dict_datatype[key]

	def run_all_tests(self):
		pass

	# <<<< GENERAL TESTS >>>>

	def test_structure(self):
		data_types_general = {"instance_id": str,
    						  "global_settings": dict,
    						  "plans": list}
		self.test_structure_dicts_datatypes(data_types_general, self.deployment_file)

	def test_typos(self):
		# TODO Add in the future
		pass

	# <<<< TEST PLANS >>>>

	def test_plan_structure(self, plan):
		data_types_plan = {'fee_asset': str,
							'markets': list,
							'plan_no': int,
							'profit_asset': str,
							'start_amount': str,
							'start_currency': str,
							'strategy': str}
		data_types_market = {'base': str,
							 'decimals': int,
							 'exchange': str,
							 'quote': str,
							 'symbol': str}

		self.test_structure_dicts_datatypes(data_types_plan, plan)
		for market in plan["markets"]:
			self.test_structure_dicts_datatypes(data_types_market, market)


	def test_plan_typos(self, plan):
		# Test that fee_asset, profit_asset, start_currency are valid assets
		assert plan["fee_asset"] in self.relevant_assets
		assert plan["profit_asset"] in self.relevant_assets
		assert plan["start_currency"] in self.relevant_assets
		# Strategy
		assert plan["strategy"] in VALID_STRATEGIES
		# Validate data for each market
		for market in plan["markets"]:
			# Test that valid-symbols are entered
			assert market["base"] + market["quote"] == market["symbol"]
			assert market["symbol"] in self.prices
			# Test that valid exchange is entered
			assert market["exchange"] in VALID_EXCHANGES

	@staticmethod
	def test_home_asset(plan):
		home_asset = plan["start_currency"]
		assert home_asset in plan["markets"][0]["symbol"]  # Path must start with home-asset sell
		assert home_asset in plan["markets"][2]["symbol"]  # Path must end with home-asset buy
		assert home_asset not in plan["markets"][1]["symbol"]  # Home-asset should't be the second one in the path

	def test_start_amount(self, plan):
		if VALID_NORMALIZATION_ASSET != plan["start_currency"]:
			symbol1 = (VALID_NORMALIZATION_ASSET + plan["start_currency"])  # Start-currency as a quote
			symbol2 = (plan["start_currency"] + VALID_NORMALIZATION_ASSET)  # Start-currency as a base
			if symbol1 in self.prices:
				price = 1 / float(self.prices[symbol1])  # Inverse price
			elif symbol2 in self.prices:
				price = float(self.prices[symbol2])
			else:
				raise Exception(f"Assets {VALID_NORMALIZATION_ASSET} and {plan['start_currency']} do not have a direct market.")
		else:
			price = 1

		assert AMOUNT_LIMIT_MIN <= float(plan["start_amount"]) * price < AMOUNT_LIMIT_MAX
	
	@staticmethod
	def test_path(plan):
		markets = plan["markets"]
		for i in range(-1, len(markets)-1):
			curr = markets[0]
			qtinnext = curr["quote"] in path[i+1]
			qtinprev = curr["quote"] not in path[i-1]
			bsinnext = curr["base"] in path[i+1]
			bsinprev = curr["base"] not in path[i-1]		
			# Quote asset needs to be included in either previous or next market, but not both
			assert qtinnext or qtinprev
			assert not (qtinnext and qtinprev)
			# Base asset needs to be included in either previous or next market, but not both
			assert bsinnext or bsinprev 
			assert not (bsinnext and bsinprev)


if __name__ == "__main__":
	path = "./data/deploymentSettings.json"
	vc = ValidityChecker(path)
	vc.gather_data()
	
	print("GENERAL TESTING".center(50, "~"))
	exceptions_gen = []
	funcs = [vc.test_structure, vc.test_typos]
	for fun in funcs:
		try:
			fun()
		except Exception as e:
			exception_str = traceback.format_exc()
			exceptions_gen.append(exception_str)

	if exceptions_gen:
		print()
		for exp in exceptions_gen:
			print(exp)
	else:
		print("OK".center(50))

	print()
	print("TESTING PLANS".center(50, "~"))
	exceptions_plans = {}
	for plan in vc.deployment_file["plans"]:
		exceptions_strs = []
		# print(str(plan["plan_no"]).ljust(4), end=" ")
		funcs = [vc.test_plan_structure, vc.test_plan_typos, vc.test_home_asset, vc.test_start_amount, vc.test_path]
		for fun in funcs:
			try:
				fun(plan)
				# print("OK")
			except Exception as e:
				# print("FAIL")
				exception_str = traceback.format_exc()
				exceptions_strs.append(exception_str)
		if exceptions_strs:
			exceptions_plans[plan["plan_no"]] = exceptions_strs
	if exceptions_plans:
		for plan_num, excs in exceptions_plans.items():
			print("\n", f"Plan {plan_num}".center(50, "."))
			for exc in excs:
				print(exc)
	else:
		print("OK".center(50))
	
