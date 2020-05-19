import json
import requests
from pprint import pprint


PRICES = {'BUY': {}, 'SELL': {}}  # Make it into a class method


def normalize_wallet(wallet_, base, side):
    # In normalization the current average price is used
    # NO NEED FOR SIDE; SIDE IS ALWAYS BIDS
    # DIFFERENT API ENDPOINT - TICKERS
    norm_wallet = wallet_
    for asset in wallet_:
        if asset == base or wallet_[asset] == 0: continue
        pair = asset + base
        if pair not in PRICES[side]:
            response = requests.get("https://api.binance.com/api/v3/ticker/bookTicker", {'symbol': pair}).json()
            price = float(response["bidPrice"])
            PRICES[side][pair] = price
        else:
            price = PRICES[side][pair]
        norm_wallet[asset] = wallet_[asset] * price

    return norm_wallet


def review_execution(op_id, responses_path):

    def rebalance(asset, qnt):
        if asset not in wallet.keys():
            wallet[asset] = qnt
        else:
            wallet[asset] += qnt

    with open(responses_path) as responses:
        response = json.load(responses)[op_id]

    wallet = {}
    orders_fills = {'BUY': {}, 'SELL': {}}

    for order in response:
        if order['side'] == 'BUY':
            money_out = -sum([float(fill['price'])*float(fill['qty']) for fill in order['fills']])
            asset_out = order['symbol'][3:]
            money_in = float(order['executedQty'])
            asset_in = order['symbol'][:3]
        else:
            money_out = -float(order['executedQty'])
            asset_out = order['symbol'][:3]
            money_in = sum([float(fill['price'])*float(fill['qty']) for fill in order['fills']])
            asset_in = order['symbol'][3:]

        fees_qnt = -sum([float(fill['commission']) for fill in order['fills']])
        fees_asset = {fill['commissionAsset'] for fill in order['fills']}
        if len(fees_asset) > 1: raise Exception('More than one fee asset.')
        # Get prices
        fills = [(fill['price'], fill['qty']) for fill in order['fills']]
        orders_fills[order['side']][order['symbol']] = fills
        rebalance(asset_out, money_out)
        rebalance(asset_in, money_in)
        rebalance(fees_asset.pop(), fees_qnt)
    norm_wallet = normalize_wallet(wallet, 'USDT', order['side'])

    return {'end_wallet': norm_wallet, 'fills': orders_fills, 'balance': sum(norm_wallet.values())}


def review_opportunity(op_id, op_path, books_path):

    def get_best_price(orders, money_in, inverse=False):
        avl = money_in
        money_out = []
        for price, amount in orders:
            price, amount = float(price), float(amount)
            diff = avl - amount
            price = 1/price if inverse else price
            if diff <= 0:
                money_out.append((price, round(avl, 5)))
                avl = 0
                break
            else:
                money_out.append((price, round(amount, 5)))
                avl -= amount
        # If not enough orders
        if avl > 0:
            raise BookTooSmall('Try again with bigger limit on the order book.')
        return money_out

    def rebalance(asset, qnt):
        if asset not in wallet.keys():
            wallet[asset] = qnt
        else:
            wallet[asset] += qnt

    with open(op_path) as opportunities:
        op = json.load(opportunities)[op_id]
    with open(books_path) as books:
        book = json.load(books)[op_id]

    instructions = op['instructions']
    if "profit" in op.keys():
        profit = op["profit"]
    elif "fees" in op.keys():
        profit = op['end_qnt'] - op['start_qnt'] - op['fees']
    else:
        profit = op["profit"]

    wallet = {}             
    orders_fills = {'BUY': {}, 'SELL': {}}
    fee_norm = 0

    for order in instructions:
        pair = order['symbol']
        book_side = book[pair]['asks'] if order['side'] == 'BUY' else book[order['symbol']]['bids']
        fills = get_best_price(book_side, order['quantity'])
        orders_fills[order['side']][pair] = fills

        if order['side'] == 'BUY':
            money_out = -sum([fill[0]*fill[1] for fill in fills])
            asset_out = pair[3:]
            money_in = sum([fill[1] for fill in fills])
            asset_in = pair[:3]
        else:
            money_out = -sum([fill[1] for fill in fills])
            asset_out = pair[:3]
            money_in = sum([fill[0]*fill[1] for fill in fills])
            asset_in = pair[3:]
        # if instructions.index(order) == (len(instructions)-1):
        #     fee_norm = op['end_qnt'] - money_in

        rebalance(asset_out, money_out)
        rebalance(asset_in, money_in)
    norm_wallet = normalize_wallet(wallet, 'USDT', order['side'])
    if "fees" in op.keys():
        fee_norm = -op['fees']
    else:
        fee_norm = -(op['end_qnt'] - op['start_qnt'])
    norm_wallet['BNB'] = fee_norm

    return {'end_wallet': norm_wallet, 'fills': orders_fills, 'balance': sum(norm_wallet.values())}


def main(*ids, save=True, show=False):
    reviews_path = '../data/reviews.json'
    responses_path = '../data/responses.json'
    books_path = '../data/books.json'
    opportunities_path = '../data/opportunities.json'

    try:
        with open(reviews_path) as reviews_file:
            reviews = json.load(reviews_file)
    except FileNotFoundError:
        reviews = {}

    valid_ids = set(ids) - set(reviews.keys())
    for op_id in valid_ids:
        execution = review_execution(op_id, responses_path)
        opportunity = review_opportunity(op_id, opportunities_path, books_path)
        reviews[op_id] = {'execution': execution, 'opportunity': opportunity}
        if show:
            pprint(reviews[op_id])
    if save:
        with open(reviews_path, 'w') as reviews_file:
            json.dump(reviews, reviews_file, indent=4)
    

if __name__ == "__main__":
    # In normalization the current average price is used
    main("15898944936", save=0, show=1)


