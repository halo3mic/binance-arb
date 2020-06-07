from binance.client import Client 

from pprint import pprint
import time

from config import *
from helpers import append_rows


def account_balances(timestamp):
	"Return account balance in markets where amount is greater than zero."
	account_info_raw = client.get_account() # Fetch account data
	account_info = {
		"id": BINANCE_PUBLIC,  # Unique account identifier - changes with new API
		"exchange": EXCHANGE,
		"timestamp": timestamp,  # Timestamp of the upload tim
		"balances": {}  # List of individual accounts balances
	}
	account_info["balances"] = [{"symbol": balance["asset"], "amount": float(balance["free"])}
								for balance in account_info_raw["balances"] 
								if float(balance["free"]) > 0
								]

	return [account_info]  # Return a list of rows to add


def latest_prices(timestamp):
	"Return latest binance price for all the available assets."
	prices_raw = client.get_all_tickers()  # Fetch last traded price for a market
	prices_rows = []
	for market in prices_raw:
		price, symbol = market["price"], market["symbol"]
		prices_row = {"timestamp": timestamp, 
				  	  "exchange": EXCHANGE, 
				      "symbol": symbol, 
				      "price": price
				      }
		prices_rows.append(prices_row)

	return prices_rows


if __name__ == "__main__":
	client = Client(api_key=BINANCE_PUBLIC, api_secret=BINANCE_SECRET)
	EXCHANGE = "binance"
	timestamp = time.time()  # In seconds since there is 0.5s diff between the calls anyway

	# Gather data
	balances_rows = account_balances(timestamp)  # Functions share timestamp so it doesn't change while fetching data
	prices_rows = latest_prices(timestamp)

	# Insert data
	error_price = append_rows(rows=prices_rows, dataset="exchanges", table="prices")
	error_balances = append_rows(rows=balances_rows, dataset="bullseye", table="balances")

	# Errors
	if error_price or error_balances:
		print("Insertion failed".center(50, "~"))
		pprint(error_price)
		pprint(error_balances)
	else:
		print("Insertion successful")
