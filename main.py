from collections import namedtuple
from datetime import datetime
from dotenv import load_dotenv
import copy
import time
import json
import os

from exceptions import BookTooSmall, StopBot
from binance import BinanceAPI
import helpers as hp
from exceptions import BinanceAPIError


class BinanceBot(BinanceAPI):

    def __init__(self, api_key, secret_key, slack_key, slack_member_id):
        super().__init__(api_key, secret_key)
        self.slack_key = slack_key
        self.slack_member_id = slack_member_id
        self.op_id = None
        self.to_slack = True
        self.execute_trade = True
        self.filter_off = False
        self.books = {}
        self.decimal_limits = {}
        self.fired_exceptions = []
        self.executions = 0
        self.chain_assets = []

    # def get_books(self, pairs, limit=10):
    #     valid_pairs = set(pairs) - set(self.books.keys())
    #     for pair in valid_pairs:
    #         self.books[pair] = self.fetch_order_book(pair, limit=limit)

    def get_decimal_limits(self, pairs):
        exhange_info = self.fetch_exchange_info()
        for symbol in exhange_info['symbols']:
            if symbol['symbol'] in pairs:
                step_size = symbol['filters'][2]['stepSize'].rstrip("0")
                self.decimal_limits[symbol['symbol']] = step_size.count("0")

    @staticmethod
    def get_best_price(orders, money_in, inverse=False):
        # Should it return tuples with amount and price?
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

    def market_price(self, pair, side, amount, limit=10, inverse=0):
        if pair not in self.books:
            self.books[pair] = self.fetch_order_book(pair, limit=limit)
        orders = self.books[pair][side]
        return self.get_best_price(orders, amount, inverse=inverse)

    def normalize_wallet(self, wallet_, base):
    # In normalization the current average price is used
    # LOOKING UP THESE BOOKS MIGHT NOT CATCH THE BEST PRICE - TICKERS?
        norm_wallet = wallet_
        for asset in wallet_:
            if asset == base or wallet_[asset] == 0: continue
            pair = [pair for pair in self.chain_assets if asset in pair and base in pair][0]  # Remove this after #17 is resolved
            price = self.market_price(pair, "bids", wallet_[asset])
            norm_wallet[asset] = wallet_[asset] * price if pair.startswith(asset) else wallet_[asset] / price

        return norm_wallet

    @staticmethod
    def interpret_chain(chain, base):
        """Interpret which pairs to buy and which to sell."""
        actions = []
        current_asset = base
        for pair in chain:
            cut = 4 if pair.startswith("USDT") else 3  # Remove this after #17 is done
            asset1 = pair[:cut]
            asset2 = pair[cut:]
            sell = asset1 == current_asset
            buy = asset2 == current_asset
            if (buy or sell) and not (buy and sell):
                action_type = "BUY" if buy else "SELL"
                actions.append((pair, action_type))
                current_asset = asset1 if buy else asset2
            else:
                raise Exception("Invalid chain.")

        return actions

    def find_trades(self, start_amount, fee, chain, base):
        """Find if chain is profitable based on fees, amount and current order books."""
        actions = self.interpret_chain(chain, base)  # Make sense of input list of pairs 
        results = self.simulate_trade(actions, start_amount, base, fee)  # Go through steps of trade to see if it would be profitable
        norm_wallet = self.normalize_wallet(results["wallet"], base)  # Convert all remaining assets to base asset
        norm_fees = self.normalize_wallet(results["fees"], base)  # Convert all fees in different assets into base one
        fees = sum(norm_fees.values())
        final_balance = sum(norm_wallet.values())  # No fees 
        result = {"instructions": results["instructions"], "final_balance": final_balance, "fees": fees}
        
        return result

    def simulate_trade(self, actions, starting_amount, start_asset, fee):

        def rebalance(wallet, asset, qnt):
            if asset not in wallet.keys():
                wallet[asset] = qnt
            else:
                wallet[asset] += qnt

        Instruction = namedtuple("Instruction", "quantity side symbol")
        instructions = []
        wallet = {start_asset: starting_amount}
        fees = {}
        holding = starting_amount

        for action in actions:
            side = {"BUY": "asks", "SELL": "bids"}[action[1]]
            # orders = self.books[action[0]][side]
            cut = 4 if action[0].startswith("USDT") else 3  # Change this after #17 is resolved
            if action[1] == 'BUY':
                price = self.market_price(action[0], side, holding, inverse=1)
                money_in_full = holding * price
                money_in = self.apply_qnt_filter(money_in_full, action[0])
                asset_in = action[0][:cut]
                money_out = money_in / price
                asset_out = action[0][cut:]
                instructions.append(Instruction(quantity=money_in, side="BUY", symbol=action[0]))
            else:
                price = self.market_price(action[0], side, holding)
                money_out_full = holding
                money_out = self.apply_qnt_filter(money_out_full, action[0])
                asset_out = action[0][:cut]
                money_in = money_out * price
                asset_in = action[0][cut:]
                instructions.append(Instruction(quantity=money_out, side="SELL", symbol=action[0]))

            rebalance(wallet, asset_out, -money_out)
            rebalance(wallet, asset_in, money_in)
            rebalance(fees, asset_in, money_in * fee)  # Is fee really on the money in?
            holding = money_in

        return {"wallet": wallet, "fees": fees, "instructions": instructions}

    # def find_oppurtunity(self, amount):
    #     # Normalize_books
    #     normalized_books = copy.deepcopy(self.eth_books)
    #     for eth_pair in self.eth_books:
    #         if eth_pair in ('ETHUSDT', 'BTCUSDT'): continue
    #         usdt_pair = [pair for pair in self.usdt_pairs if eth_pair[3:] in pair][0]
    #         buy = lambda x: x * self.market_price(self.usdt_books[usdt_pair]['asks'], x)  # Buying EUR/BUSD/USDC/TUSD
    #         sell = lambda x: x * self.market_price(self.usdt_books[usdt_pair]['bids'], x)  # Selling EUR/BUSD/USDC/TUSD
    #         normalized_books[eth_pair]['asks'] = [[buy(float(price)), amount] for price, amount in normalized_books[eth_pair]['asks']]
    #         normalized_books[eth_pair]['bids'] = [[sell(float(price)), amount] for price, amount in normalized_books[eth_pair]['bids']]

    #     best_prices = {'asks': [], 'bids': []}
    #     for pair in normalized_books:
    #         ask_price = 1/self.market_price(normalized_books[pair]['asks'], amount, inverse=True)
    #         bid_price = 1/self.market_price(normalized_books[pair]['bids'], amount, inverse=True)
    #         best_prices['asks'] += [(pair, ask_price)]
    #         best_prices['bids'] += [(pair, bid_price)]
    #     best_ask = min(best_prices['asks'], key=lambda x: x[1])
    #     best_bid = max(best_prices['bids'], key=lambda x: x[1])

    #     return {'best_ask': best_ask, 'best_bid': best_bid}

    def execute(self, instructions):
        responses = []
        for i in instructions:
            responses.append(self.submit_market_order(i.symbol, i.side, i.quantity))
        return responses

    def run_once(self, chains, base="USDT"):
        self.op_id = str(int(time.time()*10))
        start_amount = 12
        fees = 0.00075
        self.chain_assets = [chain for subchain in chains for chain in subchain]
        self.get_decimal_limits(self.chain_assets)  # Can be stored locally
        opp_found = False

        for chain in chains:
            # self.get_books(chain, limit=10)
            report = self.find_trades(start_amount, fees, chain, base)

            profit = report["final_balance"] - start_amount - report["fees"]
            if profit > 0 or self.filter_off:
                opp_found = True    
                if self.execute_trade:
                    responses = self.execute(report["instructions"])
                    self.executions += 1
                    self.save_json(responses, self.op_id, "data/responses.json")
                self.save_books()
                self.save_instructions(report["instructions"], start_amount, profit, report["fees"])
                self.output_instructions(report["instructions"], start_amount, profit, report["fees"])
                self.op_id = str(int(self.op_id) + 1)
        if not opp_found:
            print("~"*60 + "\n")
            print(datetime.now().strftime('%Y/%m/%d %H:%M:%S').center(60))
            print("NO OPPORTUNITY".center(60), end="\n\n")


    def run_loop(self, chain, base="USDT"):
        EXECUTION_LIMIT = 100
        SLACK_ALIVE_MSG_MULTIPLE = 14400
        MAX_SAME_ERRORS = 5
        LOOP_TIME = 3.3

        while 1:
            start_time = time.time()
            try:
                self.run_once(chain, base=base)
                if self.executions > EXECUTION_LIMIT: break
                if int(start_time) % SLACK_ALIVE_MSG_MULTIPLE == 0:  # Feedback about 4 times a day
                    if self.to_slack: hp.send_to_slack("Bot is alive and well! :blocky-robot:", SLACK_KEY, SLACK_MEMBER_ID, emoji=":blocky-angel:")
            except Exception as e:
                if self.to_slack and e not in self.fired_exceptions:
                    hp.send_to_slack(str(repr(e)), SLACK_KEY, SLACK_MEMBER_ID, emoji=":blocky-grin:")
                    self.fired_exceptions.append(e)
                if isinstance(e, StopBot): break
                elif self.fired_exceptions.count(e) > MAX_SAME_ERRORS:
                    break 
            sleep_time = LOOP_TIME - (time.time() - start_time)  # To prevent the ban from Binance
            if sleep_time > 0:
                time.sleep(sleep_time)

    def output_instructions(self, instructions, start_qnt, profit, fees):
        # Print the instructions in the terminal
        str_instructions = '\n'.join([f"\t{i.side} {i.quantity} {i.symbol}" for i in instructions])
        out = self.op_id + " | "
        out += datetime.now().strftime('%Y/%m/%d %H:%M:%S') + "\n"
        out += f"START: {start_qnt} USDT\n"
        out += str_instructions + "\n"
        out += f"END: {start_qnt + profit} USDT\n"
        out += f"PROFIT: {profit:.5f}"
        print("~"*60, out.center(60), sep="\n\n")
        # Send instructions to slack
        if self.to_slack: hp.send_to_slack(out, self.slack_key, self.slack_member_id)

    def save_instructions(self, instructions, start_qnt, profit, fees):
        # Save instructions in json file
        instr_dicts = []
        for i in instructions:
            instr_dicts.append(dict(i._asdict()))
        json_out = {"instructions": instr_dicts,
                    "datetime": datetime.now().strftime('%Y/%m/%d %H:%M:%S'),
                    "start_qnt": start_qnt,
                    "profit": profit,
                    "fees": fees}
        self.save_json(json_out, self.op_id, "data/opportunities.json")

    def save_books(self):
        self.save_json(self.books, self.op_id, "data/books.json")

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

    def apply_qnt_filter(self, qnt, pair, round_type='down'):
        rounding = {'even': round, 'up': hp.round_up, 'down': hp.round_down}
        rounded = rounding[round_type](float(qnt), self.decimal_limits[pair])
        return rounded




if __name__ == '__main__':
    load_dotenv()
    SECRET_KEY = os.getenv('BINANCE_SECRET')
    API_KEY = os.getenv('BINANCE_KEY')
    SLACK_KEY = os.getenv('SLACK_KEY')
    SLACK_MEMBER_ID = os.getenv('SLACK_MEMBER_ID')

    chains_eth = [["ETHUSDT", "ETHEUR", "EURUSDT"], 
                  ["EURUSDT", "ETHEUR", "ETHUSDT"]]
    chain_rub = [["ETHUSDT", "ETHRUB", "USDTRUB"], 
                 ["USDTRUB", "ETHRUB", "ETHUSDT"]]
    bot = BinanceBot(API_KEY, SECRET_KEY, SLACK_KEY, SLACK_MEMBER_ID)
    bot.run_loop(chains_eth + chain_rub)
