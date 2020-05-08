
# put money in
# store raw response
# store the order book
# store timing
# log errors
# check for different amounts - 10, 50, 100




from pprint import pprint
import json
import time

import helpers as hp

response = {'clientOrderId': 'ZQ0n4SQxsMnUvfzLA6Y88J',
      'cummulativeQuoteQty': '10.96442700',
      'executedQty': '10.25000000',
      'fills': [{'commission': '0.00000048',
                 'commissionAsset': 'BNB',
                 'price': '1.06990000',
                 'qty': '0.01000000',
                 'tradeId': 183228},
                {'commission': '0.00049317',
                 'commissionAsset': 'BNB',
                 'price': '1.06970000',
                 'qty': '10.24000000',
                 'tradeId': 183229}],
      'orderId': 1766336,
      'orderListId': -1,
      'origQty': '10.25000000',
      'price': '0.00000000',
      'side': 'SELL',
      'status': 'FILLED',
      'symbol': 'EURUSDT',
      'timeInForce': 'GTC',
      'transactTime': 1588860771145,
      'type': 'MARKET'}


def store_response(response, op_id):
	filename = "data/responses.json"
	try:
		jsonfile = open(filename, 'r')
		responses = json.load(jsonfile)
	except FileNotFoundError:
		jsonfile = open(filename, 'w')
		responses = {}
	if op_id in responses.keys():
		raise Exception("Overwritting logs!")
	responses[op_id] = response
	json.dump(responses, jsonfile)
	jsonfile.close()

# store_response(response, "OP0")
# print(str(time.time()*10))
# jsonfile = open("data/responses.json", 'r')
# responses = json.load(jsonfile)
# jsonfile.close()
while 1:
	if int(time.time()) % 600 == 0:
		break
	print(int(time.time()))
	time.sleep(0.5)

