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
            diff = avl - (amount if not inverse else amount * price)
            price = 1/price if inverse else price
            if diff <= 0:
                money_out.append((price, round(avl, 5)))
                avl = 0
                break
            else:
                money_out.append((price, round(amount, 5)))
                avl -= amount if not inverse else amount / price
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

    valid_ids = set(ids) - set(reviews.keys()) if save else ids
    for op_id in valid_ids:
        execution = review_execution(op_id, responses_path)
        opportunity = review_opportunity(op_id, opportunities_path, books_path)
        reviews[op_id] = {'execution': execution, 'opportunity': opportunity}
        if show:
            pprint(reviews[op_id])
    if save:
        with open(reviews_path, 'w') as reviews_file:
            json.dump(reviews, reviews_file, indent=4)

    return reviews
    

if __name__ == "__main__":
    # In normalization the current average price is used
    # ids = ['159061509023855208', '159061509408255208', '159061509719655208', '159061509924655208', '159061510100455208', '159061510223455208', '159061510345255208', '159061510571455208', '159061510746255208', '159061510918155208', '159061511094655208', '159061511299255208', '159061511473355208', '159061511646255208', '159061511771255208', '159061511895255208', '159061512069955208', '159061512192655208', '159061512316855208', '159061512440955208', '159061512563955208', '159061512688155208', '159061512811855208', '159061512933955208', '159061513058355208', '159061513185255208', '159061513308655208', '159061513430955208', '159061513556355208', '159061513680855208', '159061513803755208', '159061513928455208', '159061514050855208', '159061514177255208', '159061514302455208', '159061514425755208', '159061514550955208', '159061514675655208', '159061514799855208', '159061514924455208', '159061515048955208', '159061515175655208', '159061515298955208', '159061515423055208', '159061515548355208', '159061515673655208', '159061515800255208', '159061515925055208', '159061516053355208', '159061516179855208', '159061516304855208', '159061516582355208', '159061516707455208', '159061516833655208', '159061517009355208', '159061517135655208', '159061517262155208', '159061517387755208', '159061517512755208', '159061517637555208', '159061517763555208', '159061517890555208', '159061518020355208', '159061518145555208', '159061518275955208', '159061518403855208', '159061518534255208', '159061518663855208', '159061518791555208', '159061518919955208', '159061519048055208', '159061519176155208', '159061519304355208', '159061519430255208', '159061519557955208', '159061519686755208', '159061519813855208', '159061519945155208', '159061520073255208', '159061520206555208', '159061520334355208', '159061520462055208', '159061520593355208', '159061520726355208', '159061520857155208', '159061520987255208', '159061521123655208', '159061521252455208', '159061521381155208', '159061521509855208', '159061521638655208', '159061521771555208', '159061521909455208', '159061522039355208', '159061522168055208', '159061522452255208', '159061522633755208', '159062256470978216', '159062256654078216', '159062256791878216', '159062257023978216', '159062257259478216', '159062257492878216', '159062257676378216', '159062257901278216', '159062258058978216', '159062258193778216', '159062258324678216', '159062258451878216', '159062258583078216', '159062258712878216', '159062258842178216', '159062258971078216', '159062259100578216', '159062259232078216', '159062259361178216', '159062259492178216', '159062259623178216', '159062259756178216', '159062259886478216', '159062260022078216', '159062260153178216', '159062260281978216', '159062260464578216', '159062260657178216', '159062260888878216', '159062261017978216', '159062261150778216', '159062261333578216', '159062261464078216', '159062261594978216', '159062261742478216', '159062261878478216', '159062262010578216', '159062262143178216', '159062262276278216', '159062262407978216', '159062262539078216', '159062262671978216', '159062262804478216', '159062262935578216', '159062263067078216', '159062263202278216', '159062263334478216', '159062263466078216', '159062263607778216', '159062263792478216', '159062263926378216', '159062264059778216', '159062264195378216', '159062264327178216', '159062754827494760', '159062755296194760', '159062755667894760', '159062755938294760', '159062756140794760', '159062756386894760', '159062756580194760', '159062756736394760', '159062756927094760', '1590670493268-6322', '1590670640205-6614', '1590678913626-7246', '1590680437257-6169', '1590680562181-3063', '1590680657702-7851']
    with open("../data/responses.json") as file:
        opp = json.load(file)
    ids = opp.keys()
    reviews = main(*ids, save=1, show=0)
    executions = [review["execution"] for review in reviews.values()]
    plus = 0
    minus = 0
    for execution in executions:
        balance = execution["balance"]
        if balance > 0:
            pprint(execution)
            plus += balance
        else:
            minus -= balance
    print(f"Minus: {minus} | Plus: {plus}")


