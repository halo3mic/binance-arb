import json
import requests

api_limits = requests.get("https://api.binance.com/api/v1/exchangeInfo").json()
my_symbols = ['ETHUSDT', 'ETHEUR', 'EURUSDT', 'BTCUSDT', 'BTCEUR']
symbols_qnt_filter = {}
for symbol in api_limits['symbols']:
	if symbol['symbol'] in my_symbols:
		symbols_qnt_filter[symbol['symbol']] = symbol['filters'][2]

with open("../data/symbols_qnt_filter.json", "w") as file:
	json.dump(symbols_qnt_filter, file, indent=4)