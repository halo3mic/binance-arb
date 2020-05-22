import time
from binance.client import Client 
from binance.websockets import BinanceSocketManager
from twisted.internet import reactor
from collections import namedtuple
import os
import re
import atexit

import helpers as hp


PUBLIC = os.getenv("BINANCE_KEY")
SECRET = os.getenv("BINANCE_SECRET")
SLACK_KEY = os.getenv("SLACK_KEY")
SLACK_GROUP = "UHN9J9DLG"
CHAINS = [["ETHUSDT", "ETHEUR", "EURUSDT"],
          ["EURUSDT", "ETHEUR", "ETHUSDT"]]
BASE = "USDT"
START_AMOUNT = 12
FEE = 0.0007


class BinanceBot(BinanceSocketManager):

    def __init__(self, chains):
        self.client = Client(api_key=PUBLIC, api_secret=SECRET)
        self.chains = chains
        self.chain_assets = set([chain for subchain in self.chains for chain in subchain])
        self.books = self.get_intial_books(self.chain_assets)
        self.decimal_limits = self.get_decimal_limits(self.chain_assets)
        self.actions = [self.interpret_chain(chain, BASE) for chain in chains]  # Make sense of input list of pairs
        BinanceSocketManager.__init__(self, self.client)

    def handle_message(self, msg):
        if msg.get("e") == 'error':
            print("Error")
        else:
            stream = msg["stream"]
            pair = re.findall(r"^[a-z]*", stream)[0].upper()
            self.books[pair] = msg["data"]
            if len(self.books) == len(self.chain_assets):
                self.process_chain(self.books)

    def process_chain(self, books):
        # This books variable is only an address to the storage - it could get overwritten before process is finished
        timestamp = int(time.time())
        print(f"NEW DATA: {timestamp}".center(50, "~"))
        print("\n".join([f"{pair}: {book['lastUpdateId']}" for pair, book in books.items()]))
        for action in self.actions:
            print(f"Action: {action}")
            opp = self.find_opportunity(action)
            profit = opp["final_balance"] - START_AMOUNT - opp["fees"]
            print(f"Profit: {profit}")
            if profit > 0:
                msg = f"Timestamp: {timestamp}\nAction: {action}\nProfit: {profit}"
                hp.send_to_slack(msg, SLACK_KEY, SLACK_GROUP, emoji=':blocky-money:')

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

    def get_intial_books(self, pairs):
        if len(pairs) > 9:
            raise Exception("Too many pairs to process at once.")
        books = {}
        for pair in pairs:
            books[pair] = self.client.get_order_book(symbol=pair)

        return books

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

    def find_opportunity(self, action):
        """Find if chain is profitable based on fees, amount and current order books."""
        # Go through steps of trade to see if it would be profitable
        results = self.simulate_trade(action, START_AMOUNT, BASE, FEE)
        norm_wallet = self.normalize_wallet(results["wallet"], BASE)  # Convert all remaining assets to base asset
        norm_fees = self.normalize_wallet(results["fees"], BASE)  # Convert all fees in different assets into base one
        final_balance = sum(norm_wallet.values())  # No fees
        result = {"instructions": results["instructions"],
                  "final_balance": final_balance,
                  "fees": sum(norm_fees.values())
                  }
        
        return result

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
            pair = [pair for pair in self.chain_assets if asset in pair and base in pair][0]
            price = self.market_price(pair, "bids", wallet_[asset])
            norm_wallet[asset] = wallet_[asset] * price if pair.startswith(asset) else wallet_[asset] / price

        return norm_wallet

    def market_price(self, pair, side, amount, inverse=False):
        if pair not in self.books:
            raise Exception(f"Pair {pair} not in the books.")
        orders = self.books[pair][side]
        return self.get_best_price(orders, amount, inverse=inverse)

    def apply_qnt_filter(self, qnt, pair, round_type='down'):
        rounding = {'even': round, 'up': hp.round_up, 'down': hp.round_down}
        rounded = rounding[round_type](float(qnt), self.decimal_limits[pair])
        return rounded

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
            raise Exception('Try again with bigger limit on the order book.')
        return money_out/money_in


bb = BinanceBot(CHAINS)
bb.start_listening()
