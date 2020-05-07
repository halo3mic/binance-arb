import binance as bb
import itertools as it
import copy
import time
from datetime import datetime
import asyncio
import os
from dotenv import load_dotenv

from exceptions import BookTooSmall
import helpers as hp


load_dotenv()


def get_books(pairs, limit=100):
    books = {}
    for pair in pairs:
        books[pair] = bb.fetch_order_book(bb.API_KEY, pair, limit=limit)
    return books


def get_best_price(orders, money_in, inverse=False):
    # What happen if order book too small?
    avl = money_in
    money_out = 0
    for price, amount in orders:
        price, amount = float(price), float(amount)
        diff = avl - (amount if not inverse else amount*price)
        if diff <= 0:
            money_out += avl*price if not inverse else avl/price
            avl = 0 
            break
        else:
            money_out += (price*amount) if not inverse else amount
            avl -= amount if not inverse else amount*price
    # If not enough orders
    if avl > 0:
        raise BookTooSmall('Try again with bigger limit on the order book.')
    return money_out/money_in


def find_trades(amount, best_ask, best_bid, eth_books, usdt_books):
    fee = 0.00075
    ask_asset = best_ask[0][3:]
    bid_asset = best_bid[0][3:]

    msg = ""

    msg += "\t" + f"HOLDING {amount} USDT" + "\n"

    # Convert if starting asset is not in USDT
    if ask_asset != 'USDT':
        ask_asset_book = usdt_books[ask_asset + 'USDT']['asks']
        buy_amount = get_best_price(ask_asset_book, amount, inverse=1) * amount
        msg += "\t" + f"BUY {buy_amount} {ask_asset + 'USDT'}" + "\n"
        holding = buy_amount*(1-fee)
        msg += "\t" + f"HOLDING {holding} {ask_asset}" + "\n"
    else:
        holding = amount

    # Buy ETH
    buy_amount = holding*get_best_price(eth_books[best_ask[0]]['asks'], holding, inverse=1)
    holding = buy_amount*(1-fee)
    msg += "\t" + f"BUY {buy_amount} {best_ask[0]}" + "\n"
    msg += "\t" + f"HOLDING {holding} ETH" + "\n"
              
    # Sell ETH
    sell_amount = holding
    msg += "\t" + f"SELL {sell_amount} {best_bid[0]}" + "\n"
    holding = sell_amount*get_best_price(eth_books[best_bid[0]]['bids'], sell_amount)*(1-fee)
    msg += "\t" + f"HOLDING {holding} {bid_asset}" + "\n"
              
    # If asset is not in USDT convert it
    if bid_asset != 'USDT':
        msg += "\t" + f"SELL {holding} {bid_asset + 'USDT'}" + "\n"
        bid_asset_book = usdt_books[bid_asset + 'USDT']['bids']
        holding = get_best_price(bid_asset_book, holding) * holding * (1-fee)
              
    msg += "\t" + f"HOLDING: {holding}" + "\n"
    msg += "\t" + f"PROFIT: {holding - amount}"

    if holding > amount:
        hp.send_to_slack(msg, SLACK_KEY, SLACK_MEMBER_ID)
        return msg
    else:
        return "NO OPPORTUNITY"
        


def find_oppurtunity(eth_pairs, usdt_pairs, amount, eth_books, usdt_books):
    

    # Normalize_books
    normalized_books = copy.deepcopy(eth_books)
    for eth_pair in eth_books:
        if eth_pair == 'ETHUSDT': continue
        usdt_pair = [pair for pair in usdt_pairs if eth_pair[3:] in pair][0]
        buy = lambda x: x * get_best_price(usdt_books[usdt_pair]['asks'], x)  # Buying EUR/BUSD/USDC/TUSD
        sell = lambda x: x * get_best_price(usdt_books[usdt_pair]['bids'], x)  # Selling EUR/BUSD/USDC/TUSD
        normalized_books[eth_pair]['asks'] = [[buy(float(price)), amount] for price, amount in normalized_books[eth_pair]['asks']]
        normalized_books[eth_pair]['bids'] = [[sell(float(price)), amount] for price, amount in normalized_books[eth_pair]['bids']]

    best_prices = {'asks': [], 'bids': []}
    for pair in normalized_books:
        ask_price = 1/get_best_price(normalized_books[pair]['asks'], amount, inverse=1)
        bid_price = 1/get_best_price(normalized_books[pair]['bids'], amount, inverse=1)
        best_prices['asks'] += [(pair, ask_price)]
        best_prices['bids'] += [(pair, bid_price)]
    best_ask = min(best_prices['asks'], key=lambda x: x[1])
    best_bid = max(best_prices['bids'], key=lambda x: x[1])

    return {'best_ask': best_ask, 'best_bid': best_bid}


def main():
    eth_pairs = ['ETHEUR', 
                 'ETHUSDT', 
                 # 'ETHBUSD', 
                 # 'ETHUSDC', 
                 # 'ETHTUSD'
                 ]
    usdt_pairs = ['EURUSDT', 
                  # 'BUSDUSDT', 
                  # 'TUSDUSDT', 
                  # 'USDCUSDT'
                  ]
    amount = 1
    fees = 0.00075

    eth_books = get_books(eth_pairs, limit=10)
    usdt_books = get_books(usdt_pairs, limit=10)

    best_ask, best_bid = find_oppurtunity(eth_pairs, usdt_pairs, amount, eth_books, usdt_books).values()

    pairs = f"{best_ask[0]}/{best_bid[0]}"
    profit = (best_bid[1]-best_ask[1])

    msg = f"{'~'*60}\n" \
          f"{datetime.now().strftime('%Y/%m/%d %H:%M:%S')}\n" \
          f"Buy {best_ask[0]} for {best_ask[1]:.3f}\n" \
          f"Sell {best_bid[0]} for {best_bid[1]:.3f}\n" \
          f"Profit(no fees): {profit:.5f}\n" \
          f"{'~'*60}\n"
    print(msg)

    if profit > 0:
        return find_trades(amount, best_ask, best_bid, eth_books, usdt_books)
    else:
        return "NO OPPORTUNITY"



if __name__ == '__main__':
    # best_profit = ('pairs', 0)
    # logs = open('logs.txt', 'a+')
    # while 1:
        

    #     best_ask, best_bid = main(eth_pairs, usdt_pairs, amount).values()
    #     pairs = f"{best_ask[0]}/{best_bid[0]}"
    #     profit = (best_bid[1]-best_ask[1]) * (1-fees)
    #     best_profit = max((pairs, profit), best_profit, key=lambda x: x[1])

        # msg = f"{'~'*60}\n" \
        #       f"{datetime.now().strftime('%Y/%m/%d %H:%M:%S')}\n" \
        #       f"Buy {best_ask[0]} for {best_ask[1]:.3f}\nSell {best_bid[0]} for {best_bid[1]:.3f}\nProfit: {profit:.5f}\n" \
        #       f"Best profit: ({best_profit[0]}, {best_profit[1]:.5f})"

    #     print(msg)
    #     print(msg, file=logs)
    #     time.sleep(5)

    # logs.close()
    try:
        SLACK_KEY = os.getenv('SLACK_KEY')
        SLACK_MEMBER_ID = os.getenv('SLACK_MEMBER_ID')
        logs = open('logs.txt', 'a+')
        while 1:
            time1 = time.time()
            msg = main()
            if msg != 'NO OPPORTUNITY':
                out = "~"*60 + "\n"
                out += datetime.now().strftime('%Y/%m/%d %H:%M:%S') + "\n"
                out += msg
                print(out)
                print(out, file=logs)
            else:
                print(msg.center(60) + "\n")
            to_sleep = abs(3 - (time.time() - time1))
            time.sleep(to_sleep)
        logs.close()
    except Exceptions as e:
        hp.send_to_slack(str(repr(r)), SLACK_KEY, SLACK_MEMBER_ID)


