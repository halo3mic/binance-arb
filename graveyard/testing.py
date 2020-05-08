import main
from pprint import pprint
from collections import namedtuple

import csv


# Instruction = namedtuple("Instruction", "quantity side symbol")
# instructions = [
#                 Instruction(quantity=0.05348, side='BUY', symbol='ETHUSDT'),
#                 Instruction(quantity=0.05344, side='SELL', symbol='ETHEUR'),
#                  Instruction(quantity=10.25, side='SELL', symbol='EURUSDT')
#                ]

# pprint(instructions)
# pprint(main.execute(instructions))

order_responses = [
    [{'clientOrderId': 'DZl6NS9DIRIJhD7qjbY3XR',
      'cummulativeQuoteQty': '11.05966400',
      'executedQty': '0.05348000',
      'fills': [{'commission': '0.00049824',
                 'commissionAsset': 'BNB',
                 'price': '206.80000000',
                 'qty': '0.05348000',
                 'tradeId': 146137969}],
      'orderId': 1040584676,
      'orderListId': -1,
      'origQty': '0.05348000',
      'price': '0.00000000',
      'side': 'BUY',
      'status': 'FILLED',
      'symbol': 'ETHUSDT',
      'timeInForce': 'GTC',
      'transactTime': 1588860769822,
      'type': 'MARKET'},
     {'clientOrderId': 'hIEGretNjG7ylGOztlgoHo',
      'cummulativeQuoteQty': '10.28259960',
      'executedQty': '0.05348000',
      'fills': [{'commission': '0.00049570',
                 'commissionAsset': 'BNB',
                 'price': '192.27000000',
                 'qty': '0.05348000',
                 'tradeId': 103695}],
      'orderId': 4385051,
      'orderListId': -1,
      'origQty': '0.05348000',
      'price': '0.00000000',
      'side': 'SELL',
      'status': 'FILLED',
      'symbol': 'ETHEUR',
      'timeInForce': 'GTC',
      'transactTime': 1588860770487,
      'type': 'MARKET'},
     {'clientOrderId': 'ZQ0n4SQxsMnUvfzLA6Y88J',
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
      'type': 'MARKET'}]
 ]

responses2 = []
for response in order_responses[0]:
	fieldnames = {'clientOrderId', 
                  'executedQty', 
                  'price',
                  'fee'
                  'fee_asset',
                  'orderId', 
                  'origQty',  
                  'side', 
                  'status', 
                  'symbol', 
                  'timeInForce', 
                  'transactTime', 
                  'type'
                  }
with open('tx_logs.csv', 'w') as tx_logs:
    fieldnames = ['clientOrderId', 
                  'executedQty', 
                  'price', 
                  'orderId', 
                  'origQty',  
                  'side', 
                  'status', 
                  'symbol', 
                  'timeInForce', 
                  'transactTime', 
                  'type'
                  ]
    writer = csv.DictWriter(tx_logs, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerow(order_responses[0][3])

