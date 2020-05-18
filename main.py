from collections import namedtuple
from datetime import datetime
from dotenv import load_dotenv
import copy
import time
import json
import os

from exceptions import BookTooSmall
from binance import BinanceAPI
import helpers as hp
from exceptions import BinanceAPIError


class BinanceBot(BinanceAPI):

    def __init__(self, eth_pairs, usdt_pairs, api_key, secret_key, slack_key, slack_member_id):
        super().__init__(api_key, secret_key)
        self.eth_pairs = eth_pairs
        self.usdt_pairs = usdt_pairs
        self.eth_books = {}
        self.usdt_books = {}
        self.slack_key = slack_key
        self.slack_member_id = slack_member_id
        self.op_id = None
        self.to_slack = True
        self.execute_trade = True
        self.filter_off = False

    def get_books(self, pairs, limit=100):
        books = {}
        for pair in pairs:
            books[pair] = self.fetch_order_book(pair, limit=limit)
        return books

    @staticmethod
    def get_best_price(orders, money_in, inverse=False):
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

    def find_trades(self, amount, fee, best_ask_asset, best_bid_asset):
        fees_total = 0  # In USDT
        ask_asset = best_ask_asset[3:]
        bid_asset = best_bid_asset[3:]

        Instruction = namedtuple("Instruction", "quantity side symbol")
        instructions = []

        # Convert if starting asset is not in USDT
        if ask_asset != 'USDT':
            pair = ask_asset + 'USDT'
            ask_asset_book = self.usdt_books[pair]['asks']
            price = self.get_best_price(ask_asset_book, amount, inverse=True)
            buy_amount = price * amount
            buy_amount = self.apply_qnt_filter(buy_amount, pair)
            # Start amount is not the amount this program is set to. 
            # This is because we have to base order no on amount we have, but on the amount we want. 
            # And accuracy of that is limited with allowed decimal points.
            start_amount = buy_amount / price
            instructions.append(Instruction(quantity=buy_amount, side='BUY', symbol=pair))
            holding = buy_amount
            fees_total += buy_amount * fee
        else:
            holding = amount

        # Buy ETH
        price = self.get_best_price(self.eth_books[best_ask_asset]['asks'], holding, inverse=True)
        buy_amount = holding * price
        buy_amount = self.apply_qnt_filter(buy_amount, best_ask_asset)
        # Start amount is not the amount this program is set to. 
        # This is because we have to base order no on amount we have, but on the amount we want. 
        # And accuracy of that is limited with allowed decimal points.
        if ask_asset == 'USDT':
            start_amount = buy_amount / price
        instructions.append(Instruction(quantity=buy_amount, side='BUY', symbol=best_ask_asset))
        fees_total += holding * fee
        holding = buy_amount

        # Sell ETH
        sell_amount = self.apply_qnt_filter(holding, best_bid_asset)
        instructions.append(Instruction(quantity=sell_amount, side='SELL', symbol=best_bid_asset))
        price_ = self.get_best_price(self.eth_books[best_bid_asset]['bids'], sell_amount)
        holding = sell_amount * price_
        fees_total += holding * fee

        # If asset is not in USDT convert it
        if bid_asset != 'USDT':
            pair = bid_asset + 'USDT'
            sell_amount = self.apply_qnt_filter(holding, pair)
            instructions.append(Instruction(quantity=sell_amount, side='SELL', symbol=pair))
            bid_asset_book = self.usdt_books[pair]['bids']
            holding = self.get_best_price(bid_asset_book, sell_amount) * sell_amount
            fees_total += holding * fee

        return {"instructions": instructions, "start_amount": start_amount, "end_amount": holding, "fees": fees_total}

    def find_oppurtunity(self, amount):
        # Normalize_books
        normalized_books = copy.deepcopy(self.eth_books)
        for eth_pair in self.eth_books:
            if eth_pair in ('ETHUSDT', 'BTCUSDT'): continue
            usdt_pair = [pair for pair in self.usdt_pairs if eth_pair[3:] in pair][0]
            buy = lambda x: x * self.get_best_price(self.usdt_books[usdt_pair]['asks'], x)  # Buying EUR/BUSD/USDC/TUSD
            sell = lambda x: x * self.get_best_price(self.usdt_books[usdt_pair]['bids'], x)  # Selling EUR/BUSD/USDC/TUSD
            normalized_books[eth_pair]['asks'] = [[buy(float(price)), amount] for price, amount in normalized_books[eth_pair]['asks']]
            normalized_books[eth_pair]['bids'] = [[sell(float(price)), amount] for price, amount in normalized_books[eth_pair]['bids']]

        best_prices = {'asks': [], 'bids': []}
        for pair in normalized_books:
            ask_price = 1/self.get_best_price(normalized_books[pair]['asks'], amount, inverse=True)
            bid_price = 1/self.get_best_price(normalized_books[pair]['bids'], amount, inverse=True)
            best_prices['asks'] += [(pair, ask_price)]
            best_prices['bids'] += [(pair, bid_price)]
        best_ask = min(best_prices['asks'], key=lambda x: x[1])
        best_bid = max(best_prices['bids'], key=lambda x: x[1])

        return {'best_ask': best_ask, 'best_bid': best_bid}

    def execute(self, instructions):
        responses = []
        for i in instructions:
            responses.append(self.submit_market_order(i.symbol, i.side, i.quantity))
        return responses

    def run_once(self):
        self.op_id = str(int(time.time()*10))
        amount = 12
        fees = 0.00075

        self.eth_books = self.get_books(self.eth_pairs, limit=10)
        self.usdt_books = self.get_books(self.usdt_pairs, limit=10)
        # best_ask, best_bid = self.find_oppurtunity(amount).values()
        # no_fee_profit = best_bid[1] - best_ask[1]

        # if no_fee_profit > 0 or self.filter_off:
        #     found_trades = self.find_trades(amount, fees, best_ask[0], best_bid[0])
        self.save_books()
        for i in (0, -1):
            pairs = ("ETHUSDT", "ETHEUR")
            found_trades = self.find_trades(amount, fees, pairs[i], pairs[i+1])
            start_amount = found_trades['start_amount']
            holding = found_trades['end_amount']
            instructions = found_trades['instructions']
            fees = found_trades['fees']
            profit = holding - start_amount - fees
            self.save_instructions(instructions, start_amount, holding, fees)
            if profit > 0 or self.filter_off:
                if self.execute_trade:
                    responses = self.execute(instructions)
                    self.save_json(responses, self.op_id, "data/responses.json")
                self.output_instructions(instructions, start_amount, holding, fees)
            else:
                self.print_no_op()
            self.op_id = str(int(self.op_id) + 1)
        # else:
        #     self.print_no_op()

    @staticmethod
    def print_no_op():
        print("~"*60 + "\n")
        print(datetime.now().strftime('%Y/%m/%d %H:%M:%S').center(60))
        print("NO OPPORTUNITY".center(60), end="\n\n")

    def run_loop(self):
        while 1:
            try:
                start_time = time.time()
                self.run_once()
                sleep_time = abs(3 - (time.time() - start_time))  # Needs to sleep at least 3 sec for making 3 calls
                time.sleep(sleep_time)
                if int(start_time) % 14400 == 0:  # Feedback about 4 times a day
                    if self.to_slack: hp.send_to_slack("Bot is alive and well! :blocky-robot:", SLACK_KEY, SLACK_MEMBER_ID, emoji=":blocky-angel:")
            except Exception as e:
                if self.to_slack: hp.send_to_slack(str(repr(e)), SLACK_KEY, SLACK_MEMBER_ID, emoji=":blocky-grin:")
                # if isinstance(e, BinanceAPIError):
                #     break

    def output_instructions(self, instructions, start_qnt, end_qnt, fees):
        # Print the instructions in the terminal
        str_instructions = '\n'.join([f"\t{i.side} {i.quantity} {i.symbol}" for i in instructions])
        out = self.op_id + " | "
        out += datetime.now().strftime('%Y/%m/%d %H:%M:%S') + "\n"
        out += f"START: {start_qnt} USDT\n"
        out += str_instructions + "\n"
        out += f"END: {end_qnt} USDT\n"
        out += f"PROFIT: {end_qnt-start_qnt-fees:.5f}"
        print("~"*60, out.center(60), sep="\n\n")
        # Send instructions to slack
        if self.to_slack: hp.send_to_slack(out, self.slack_key, self.slack_member_id)

    def save_instructions(self, instructions, start_qnt, end_qnt, fees):
        # Save instructions in json file
        instr_dicts = []
        for i in instructions:
            instr_dicts.append(dict(i._asdict()))
        json_out = {"instructions": instr_dicts,
                    "datetime": datetime.now().strftime('%Y/%m/%d %H:%M:%S'),
                    "start_qnt": start_qnt,
                    "end_qnt": end_qnt,
                    "fees": fees}
        self.save_json(json_out, self.op_id, "data/opportunities.json")

    def save_books(self):
        books = {**self.usdt_books, **self.eth_books}
        self.save_json(books, self.op_id, "data/books.json")

    @staticmethod
    def save_json(content, key, filename):
        try:
            with open(filename, 'r') as jsonfile:
                data = json.load(jsonfile)
        except FileNotFoundError:
            data = {}
        jsonfile = open(filename, 'w')
        if key in data.keys():
            raise Exception("Overwritting!")
        data[key] = content
        json.dump(data, jsonfile, indent=4)
        jsonfile.close()

    @staticmethod
    def apply_qnt_filter(qnt, pair, round_type='down'):
        with open("data/symbols_qnt_filter.json") as file:
            c = json.load(file)
            min_qnt = c[pair]['stepSize'].rstrip("0")
            dec = min_qnt.count("0")
            rounding = {'even': round, 'up': hp.round_up, 'down': hp.round_down}
            rounded = rounding[round_type](float(qnt), dec)
        return rounded


if __name__ == '__main__':
    load_dotenv()
    SECRET_KEY = os.getenv('BINANCE_SECRET')
    API_KEY = os.getenv('BINANCE_KEY')
    SLACK_KEY = os.getenv('SLACK_KEY')
    SLACK_MEMBER_ID = os.getenv('SLACK_MEMBER_ID')

    eth_pairs = ['ETHEUR',
                 'ETHUSDT',
                 # 'ETHBUSD',
                 # 'ETHUSDC',
                 # 'ETHTUSD'
                 ]
    # btc_pairs = ['BTCEUR',
    #              'BTCUSDT'
    #             ]
    usdt_pairs = ['EURUSDT',
                  # 'BUSDUSDT',
                  # 'TUSDUSDT',
                  # 'USDCUSDT'
                  ]
    bot = BinanceBot(eth_pairs, usdt_pairs, API_KEY, SECRET_KEY, SLACK_KEY, SLACK_MEMBER_ID)
    bot.run_loop()
