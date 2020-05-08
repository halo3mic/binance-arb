# def get_avg_price(elements): 
# 	numerator = 0
# 	denominator = 0
# 	for element in elements:
# 		numerator += float(element[0])*float(element[1])
# 		denominator += float(element[0])
# 	avg = numerator / denominator

# 	return avg


# # Average price
# _price_qnt = [(fill['qty'], fill['price']) for fill in response['fills']]
# avg_price = get_avg_price(_price_qnt)
# # Fee information
# total_fee = None  # Can't sum different assets
# fee_asset = list({fill['commissionAsset'] for fill in response['fills']})
# # Profit
# if response['type'] == 'BUY':
# 	end_amount = sum([float(fill['qty'])*float(fill['price']) for fill in response['fills']])
# else:
# 	end_amount = sum([float(fill['qty'])/float(fill['price']) for fill in response['fills']])
# profit = end_amount - float(response['origQty'])

# order = {
# 	'orderId': response['clientOrderId'],  # clientOrderId given by Binance
# 	'timstamp': response['transactTime'],  # Time of execution in epoch
# 	'avg_price': avg_price,  # Price over all fills (asset_out/asset_in)
# 	'total_fee': total_fee,  # Fee over all fills (in fee_asset)
# 	'fee_asset': fee_asset,  # Asset in which fee was executed
# 	'status': response['status'],  # Status of the order
# 	'type': response['type'],  # Type of order (MARKET/LIMIT/...)
# 	'side': response['side'],  # BUY or SELL
# 	'start_amount': float(response['origQty']),  # Starting amount in base asset
# 	'executed_amount': float(response['executedQty']),  # How much of start_amount was filled
# 	}