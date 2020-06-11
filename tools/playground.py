from pprint import pprint
import time

from dummy_data import RESPONSES, BOOKS
from helpers import append_rows


PLATFORM = "BINANCE"
opportunity_timestamp = time.time()
opportunity_id = "1591519412039-2963"


def log_responses(responses):
	responses_rows = []
	for response in responses:
		response["id"] = hash(str(response["orderId"]) + response["symbol"] + PLATFORM)
		response["exchangeTimestamp"] = response["transactTime"] / 10**3
		response["localTimestamp"] = opportunity_timestamp
		response["exchange"] = PLATFORM
		response["opportunityId"] = opportunity_id
		del response["clientOrderId"]
		del response["transactTime"]
		del response["orderListId"]
		del response["cummulativeQuoteQty"]
		responses_rows.append(response)
	errors = append_rows(rows=responses_rows, dataset="bullseye", table="trades")

	return errors


def log_opportunity():
	opportunity = {
		"id": opportunity_id,
		"foundAtTimestamp": opportunity_timestamp,
		"amountIn": 12,
		"estimatedAmountOutAfterFee": 12.003,
		"fee": 0.027
		}
	errors = append_rows(rows=[opportunity], dataset="bullseye", table="opportunities")

	return errors


def log_books(books):
	books_rows = []
	for symbol, book in books.items():
		book_row = {
		"id": hash(str(book["lastUpdateId"]) + symbol + PLATFORM),
		"receivedAtTimestamp": book["timestamp"],
		"opportunityId": opportunity_id,
		"exchange": PLATFORM,
		"symbol": symbol,
		"bids": [{"price": order[0], "qty": order[1]} for order in book["bids"]],
		"asks": [{"price": order[0], "qty": order[1]} for order in book["asks"]]
		}
		books_rows.append(book_row)

	pprint(books_rows)
	return books_rows


if __name__ == "__main__":
	rows = log_books(BOOKS)
	errors = append_rows(rows=rows, dataset="bullseye", table="books")
	print(errors)