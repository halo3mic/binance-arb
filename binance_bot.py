import time
from binance.client import Client 
from binance.websockets import BinanceSocketManager
from twisted.internet import reactor
from collections import namedtuple
import re
import atexit
from datetime import datetime

import helpers as hp
from config import *


class BinanceBot(BinanceSocketManager):

    def __init__(self, chains, base, start_amount, execute=True, test_it=False):
        self.client = Client(api_key=BINANCE_PUBLIC, api_secret=BINANCE_SECRET)
        self.chains = chains
        self.base = base
        self.start_amount = start_amount
        self.execute = execute
        self.test_it = test_it

        self.busy = False  # Is the bot currently handling one of the books
        self.chain_assets = set([chain for subchain in self.chains for chain in subchain])
        # self.books = self.get_intial_books(self.chain_assets)
        self.books = {}
        self.decimal_limits = self.get_decimal_limits(self.chain_assets)
        self.actions = [self.interpret_chain(chain, base) for chain in chains]  # Make sense of input list of pairs
        BinanceSocketManager.__init__(self, self.client)

    def handle_message(self, msg):
        if msg.get("e") == 'error':
            raise Exception("Stream error")
        elif not self.busy:
            self.busy = True
            stream = msg["stream"]
            pair = re.findall(r"^[a-z]*", stream)[0].upper()
            self.books[pair] = msg["data"]
            if len(self.books) == len(self.chain_assets):
                self.process_chain(self.books)
            self.busy = False

    def process_chain(self, books):
        # This books variable is only an address to the storage - it could get overwritten before process is finished
        os.system("clear")
        timestamp = int(time.time())
        print(f"NEW DATA: {timestamp}".center(50, "~"))
        print("\n".join([f"{pair}: {book['lastUpdateId']}" for pair, book in books.items()]))
        for action in self.actions:
            print(f"Action: {action}")
            opportunity = Opportunity(self, action)
            opportunity.find_opportunity()

            print(f"Profit: {opportunity.profit}")
            if opportunity.profit > 0 or self.test_it:
                if self.execute:
                    opportunity.execute()
                opportunity.to_slack()
                opportunity.save()
                hp.save_json(self.books, opportunity.id, BOOKS_SOURCE)
                if self.test_it:
                    # self.upon_closure()  # If testing, exit after an opportunity
                    os._exit(1)
                break  # The execution and saving slows takes some time, in which the order book can already change

    def start_listening(self):
        stream_names = [pair.lower() + "@depth10@100ms" for pair in self.chain_assets]
        self.start_multiplex_socket(stream_names, self.handle_message)
        self.start()
        atexit.register(self.upon_closure)  # Close the sockets when you close the terminal

    def upon_closure(self):
        self.close()
        reactor.stop()
        print("GOODBYE!")

    def get_decimal_limits(self, pairs):
        exhange_info = self.client.get_exchange_info()
        decimal_limits = {}
        for symbol in exhange_info['symbols']:
            if symbol['symbol'] in pairs:
                step_size = symbol['filters'][2]['stepSize'].rstrip("0")
                decimal_limits[symbol['symbol']] = step_size.count("0")

        return decimal_limits

    # def get_intial_books(self, pairs):
    #     if len(pairs) > 9:
    #         raise Exception("Too many pairs to process at once.")
    #     books = {}
    #     for pair in pairs:
    #         books[pair] = self.client.get_order_book(symbol=pair)
    #
    #     return books

    @staticmethod
    def interpret_chain(chain, base):
        """Interpret which pairs to buy and which to sell."""
        actions = []
        current_asset = base
        for pair in chain:
            # Remove this after #17 is done
            cut = 4 if pair.startswith("USDT") or pair.startswith("USDC") else 5 if pair.startswith("STORM") else 3
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

    def execute_order(self, instruction):
        market_order = {"BUY": self.client.order_market_buy, "SELL": self.client.order_market_sell}[instruction.side]
        response = market_order(symbol=instruction.symbol, quantity=instruction.quantity)

        return response


class Opportunity:

    def __init__(self, bot, action):
        self.bot = bot
        self.action = action

        self.profit = None
        self.instructions = None
        self.final_balance = None
        self.fees = None
        self.id = str(int(time.time()*1000)) + str(id(action))[10:]

    def find_opportunity(self):
        """Find if chain is profitable based on fees, amount and current order books."""
        # Go through steps of trade to see if it would be profitable
        results = self.simulate_trade(self.action, self.bot.start_amount, self.bot.base, FEE)
        norm_wallet = self.normalize_wallet(results["wallet"], self.bot.base)  # Convert all remaining assets to base asset
        norm_fees = self.normalize_wallet(results["fees"], self.bot.base)  # Convert all fees in different assets into base one
        final_balance = sum(norm_wallet.values())  # No fees
        self.instructions = results["instructions"]
        self.final_balance = final_balance
        self.fees = sum(norm_fees.values())
        self.profit = self.final_balance - self.bot.start_amount - self.fees

    def simulate_trade(self, actions, starting_amount, start_asset, fee):

        def rebalance(wallet_, asset, qnt):
            if asset not in wallet_.keys():
                wallet_[asset] = qnt
            else:
                wallet_[asset] += qnt

        Instruction = namedtuple("Instruction", "quantity side symbol")
        instructions = []
        wallet = {start_asset: starting_amount}
        fees = {}
        holding = starting_amount

        for action in actions:
            side = {"BUY": "asks", "SELL": "bids"}[action[1]]
            # orders = self.books[action[0]][side]
            # Change this after #17 is resolved
            cut = 4 if action[0].startswith("USDT") else 5 if action[0].startswith("STORM") else 3
            if action[1] == 'BUY':
                price = self.market_price(action[0], side, holding, inverse=True)
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

    def normalize_wallet(self, wallet_, base):
        # In normalization the current average price is used
        # LOOKING UP THESE BOOKS MIGHT NOT CATCH THE BEST PRICE - TICKERS?
        norm_wallet = wallet_
        for asset in wallet_:
            if asset == base or wallet_[asset] == 0: continue
            # Remove this after #17 is resolved
            pair = [pair for pair in self.bot.chain_assets if asset in pair and base in pair][0]
            price = self.market_price(pair, "bids", wallet_[asset])
            norm_wallet[asset] = wallet_[asset] * price if pair.startswith(asset) else wallet_[asset] / price

        return norm_wallet

    def market_price(self, pair, side, amount, inverse=False):
        if pair not in self.bot.books:
            raise Exception(f"Pair {pair} not in the books.")
        orders = self.bot.books[pair][side]
        return self.get_best_price(orders, amount, inverse=inverse)

    def apply_qnt_filter(self, qnt, pair, round_type='down'):
        rounding = {'even': round, 'up': hp.round_up, 'down': hp.round_down}
        rounded = rounding[round_type](float(qnt), self.bot.decimal_limits[pair])
        return rounded

    @staticmethod
    def get_best_price(orders, money_in, inverse=False):
        # Should it return tuples with amount and price?
        avl = money_in
        money_out = 0
        for price, amount in orders:
            price, amount = float(price), float(amount)
            diff = avl - (amount if not inverse else amount * price)
            if diff <= 0:
                money_out += avl * price if not inverse else avl / price
                avl = 0
                break
            else:
                money_out += (price * amount) if not inverse else amount
                avl -= amount if not inverse else amount * price
        # If not enough orders
        if avl > 0:
            raise Exception('Try again with bigger limit on the order book.')
        return money_out / money_in

    def to_slack(self):
        msg = f"_Opportunity ID:_ *{self.id}*\n" \
              f"_Action:_ *{' | '.join([step[0] + '-' + step[1] for step in self.action])}*\n" \
              f"_Profit:_ *{self.profit:.5f}*\n" \
              f"_Executed:_ *{self.bot.execute}*\n" \
              f"_Start amount:_ *{self.bot.start_amount} {self.bot.base}*"

        hp.send_to_slack(msg, SLACK_KEY, SLACK_GROUP, emoji=':blocky-money:')

    def save(self):
        # Save instructions in json file
        instr_dicts = []
        for i in self.instructions:
            instr_dicts.append(dict(i._asdict()))
        json_out = {"instructions": instr_dicts,
                    "datetime": datetime.now().strftime('%Y/%m/%d %H:%M:%S'),
                    "start_qnt": self.bot.start_amount,
                    "profit": self.profit,
                    "fees": self.fees}
        hp.save_json(json_out, self.id, OPPORTUNITIES_SOURCE)

    def execute(self):
        responses = []
        for instruction in self.instructions:
            market_order = {"BUY": self.bot.client.order_market_buy, "SELL": self.bot.client.order_market_sell}[instruction.side]
            response = market_order(symbol=instruction.symbol, quantity=instruction.quantity)
            responses.append(response)
        hp.save_json(responses, self.id, RESPONSES_SOURCE)

        return responses
