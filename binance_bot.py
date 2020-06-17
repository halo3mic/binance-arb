import time
from binance.client import Client, BinanceAPIException
from binance.websockets import BinanceSocketManager
from threading import Thread
from twisted.internet import reactor
from collections import namedtuple
import concurrent.futures
import re
import atexit
import json
from pprint import pprint

import helpers as hp
from config import *


class BinanceBot(BinanceSocketManager):

    def __init__(self, plans, execute=True, test_it=False, loop=True, settings=None):
        self.slack_group = SLACK_GROUP if not test_it else SLACK_GROUP_TEST
        # TODO Add keys as attributes

        self.client = Client(api_key=BINANCE_PUBLIC, api_secret=BINANCE_SECRET)
        # Conditions
        self.execute = execute  # If false no opportunity gets executed
        self.test_it = test_it  # Opportunity gets executed even if unprofitable
        self.loop = loop  # If false it will only check one book update
        self.busy = False  # Is the bot currently handling one of the books
        # self.settings = settings

        self.plans = plans
        self.plan_markets = set([market for plan in plans for market in plan.path])
        self.books = {}
        # self.books = {}
        self.process_books = {}
        self.current_statuses = {}
        self.last_book_update = None
        self.exceptions = []

        BinanceSocketManager.__init__(self, self.client)

    def handle_message(self, msg):
        if msg.get("e") == 'error':
            hp.send_to_slack(str(msg), SLACK_KEY, SLACK_GROUP, emoji=':blocky-sweat:')
        pair = re.findall(r"^[a-z]*", msg["stream"])[0].upper()
        self.books[pair] = msg["data"]  # Save new books (overwrite the old ones)
        self.books[pair]["timestamp"] = time.time()
        self.last_book_update = time.time()
        # If not busy and all assets books are available
        if not self.busy and len(self.books) == len(self.plan_markets):
            self.busy = True
            self.process_books = self.books.copy()
            Thread(target=self.process_plans, args=(pair,)).start()
        # Take all the exceptions from threads and message them to Slack group
        if self.exceptions:
            msg = " >" + "\n".join([str(exc) for exc in self.exceptions])
            hp.send_to_slack(msg, SLACK_KEY, self.slack_group, emoji=':blocky-money:')

    def process_plans(self, pair):
        try:
            valid_plans = [plan for plan in self.plans if pair in plan.path]  # Only proccess plans which include updated market
            os.system("clear")
            timestamp = int(time.time())
            print(f"NEW DATA: {timestamp}".center(50, "~"))
            for plan in valid_plans:
                opportunity = Opportunity(self, plan)
                opportunity.find_opportunity()
                if opportunity.profit > 0 or self.test_it:
                    if self.execute:
                        responses = opportunity.execute(async_=True)
                        if self.loop:
                            self.busy = False  # Remove the lock 
                        opportunity.actual_profit = format(opportunity.review_execution(responses)["balance"], ".8f") + " " + opportunity.plan.home_asset
                        opportunity.log_responses(responses)
                    opportunity.log_opportunity()
                    opportunity.log_books()
                    opportunity.to_slack()

        except Exception as e:
            self.exceptions.append(e)
            if self.loop:
                self.busy = False


    def start_listening(self):
        stream_names = [pair.lower() + "@depth10@100ms" for pair in self.plan_markets]
        self.start_multiplex_socket(stream_names, self.handle_message)
        if not reactor.running: self.start()
        atexit.register(self.upon_closure)  # Close the sockets when you close the terminal
        self.books = self.get_intial_books(self.plan_markets)  # Get initial books
        self.last_book_update = time.time()


    def upon_closure(self):
        self.close()
        if reactor.running: reactor.stop()
        print("GOODBYE!")

    def get_intial_books(self, pairs):
        print("Fetching initial books".center(80, "~"))
        t1 = time.time()
        # if len(pairs) > 9:
        #     raise Exception("Too many pairs to process at once.")
        books = {}
        counter = 0
        for pair in pairs:
            print(f"{pair} fetched!")
            books[pair] = self.client.get_order_book(symbol=pair)
            books[pair]["timestamp"] = time.time()
            if counter == 5 and (time.time()-t1 < 1):
                time.sleep(1)
                counter = 0
                t1 = time.time()
            else:
                counter += 1
        print(f"Finished! Time taken: {time.time() - t1} sec.")

        return books


class Opportunity:

    def __init__(self, bot, plan):
        self.bot = bot
        self.plan = plan

        self.profit = None
        self.instructions = None
        self.final_balance = None
        self.fees = None
        self.execution_time = None
        self.actual_profit = None
        self.success_ratio = None
        self.execution_msg = ""
        self._async = False
        self.execution_status = "NOT EXECUTED"
        self.timestamp = time.time()
        self.id = f"{str(int(self.timestamp*1000))}-{str(hash(str([action.symbol for action in plan.actions])))[-4:]}"

    def find_opportunity(self):
        """Find if chain is profitable based on fees, amount and current order books."""
        # Go through steps of trade to see if it would be profitable
        results = self.simulate_trade(self.plan.actions, self.plan.start_amount, self.plan.home_asset, FEE)
        norm_wallet = self.normalize_wallet(results["wallet"], self.plan.home_asset)  # Convert all remaining assets to base asset
        norm_fees = self.normalize_wallet(results["fees"], self.plan.home_asset)  # Convert all fees in different assets into base one
        final_balance = sum(norm_wallet.values())  # No fees
        self.instructions = results["instructions"]
        self.final_balance = final_balance
        self.fees = sum(norm_fees.values())
        self.profit = self.final_balance - self.plan.start_amount - self.fees

    def simulate_trade(self, actions, starting_amount, start_asset, fee):

        def rebalance(wallet_, asset, qnt):
            if asset not in wallet_.keys():
                wallet_[asset] = qnt
            else:
                wallet_[asset] += qnt

        Instruction = namedtuple("Instruction", "price amount side symbol")
        instructions = []
        wallet = {start_asset: starting_amount}
        fees = {}
        holding = starting_amount

        for action in actions:
            side = {"BUY": "asks", "SELL": "bids"}[action.side]

            if action.side == 'BUY':
                best_orders, price = self.market_price(action.symbol, side, holding, inverse=True)
                worst_price = max(best_orders, key=lambda x: x[0])[0]
                money_in_full = holding * price
                money_in = self.apply_qnt_filter(money_in_full, action)
                asset_in = action.base
                money_out = money_in / price
                asset_out = action.quote
                instructions.append(Instruction(price=worst_price, amount=money_in, side="BUY", symbol=action.symbol))
            else:
                best_orders, price = self.market_price(action.symbol, side, holding)
                worst_price = min(best_orders, key=lambda x: x[0])[0]
                money_out_full = holding
                money_out = self.apply_qnt_filter(money_out_full, action)
                asset_out = action.base
                money_in = money_out * price
                asset_in = action.quote
                instructions.append(Instruction(price=worst_price, amount=money_out, side="SELL", symbol=action.symbol))
            rebalance(wallet, asset_out, -money_out)
            rebalance(wallet, asset_in, money_in)
            rebalance(fees, asset_in, money_in * fee)  # Is fee really on the money in?
            holding = money_in

        return {"wallet": wallet, "fees": fees, "instructions": instructions}

    def normalize_wallet(self, wallet_, normalizing_to):
        # In normalization the current average price is used
        # LOOKING UP THESE BOOKS MIGHT NOT CATCH THE BEST PRICE - TICKERS?
        norm_wallet = wallet_
        for asset in wallet_:
            if asset == normalizing_to or wallet_[asset] == 0: continue
            if asset+normalizing_to in self.bot.plan_markets:
                pair = asset+normalizing_to
                inverse = False
            else:
                pair = normalizing_to+asset
                inverse = True
            _, price = self.market_price(pair, "bids", wallet_[asset], inverse=inverse)  # TODO It is not always "bids"
            norm_wallet[asset] = wallet_[asset] * price

        return norm_wallet

    def market_price(self, pair, side, amount, inverse=False):
        if pair not in self.bot.process_books:
            raise Exception(f"Pair {pair} not in the books.")
        orders = self.bot.process_books[pair][side]
        return self.get_best_orders(orders, amount, inverse=inverse)

    def apply_qnt_filter(self, qnt, action, round_type='down'):
        rounding = {'even': round, 'up': hp.round_up, 'down': hp.round_down}
        rounded = rounding[round_type](float(qnt), action.decimals)
        return rounded

    @staticmethod
    def get_best_orders(orders, money_in, inverse=False):
        avl = money_in
        money_out = []
        for price, amount in orders:
            price, amount = float(price), float(amount)
            diff = avl - (amount if not inverse else amount * price)
            # price = 1 / price if inverse else price
            if diff <= 0:
                avl = avl if not inverse else avl / price
                money_out.append((price, avl))
                avl = 0
                break
            else:
                money_out.append((price, amount))
                avl -= amount if not inverse else amount * price
        # If not enough orders
        if avl > 0:
            raise Exception('Try again with bigger limit on the order book.')
        price = hp.get_avg(money_out)
        price = 1/price if inverse else price
        return money_out, price

    def to_slack(self):
        if self.execution_status != "PASS":
            self.actual_profit = "*" + self.actual_profit
        action_separator = " | " if self._async else " > "
        msg = f"_Opportunity ID:_ *{self.id}*\n" \
              f"_Action:_ *{action_separator.join([(step.symbol + '-' + step.side) for step in self.plan.actions])}*\n" \
              f"_EstimatedProfit:_ *{self.profit:.8f} {self.plan.home_asset}*\n" \
              f"_ActualProfit:_ * {self.actual_profit}*\n" \
              f"_Start timestamp:_ *{self.id[:-5]}*\n" \
              f"_End timestamp:_ *{int(time.time()*1000)}*\n" \
              f"_OrdersExecution time:_ *{self.execution_time}*\n" \
              f"_Status_: *{self.execution_msg}*\n" \
              f"_Start amount:_ *{self.plan.start_amount} {self.plan.home_asset}*\n"
        hp.send_to_slack(msg, SLACK_KEY, self.bot.slack_group, emoji=':blocky-money:')

    def execute(self, async_=False):
        self._async = async_
        start_time = time.perf_counter_ns()
        responses = self._execute_async() if async_ else self._execute_sync()
        if not responses:
            return None
        self.execution_time = str(time.perf_counter_ns() - start_time)[:-6] + " ms"
        
        return responses

    def _execute_sync(self):
        # TODO Needs to be updated
        responses = []
        for instruction in self.instructions:
            response = self.bot.client.create_order(symbol=instruction.symbol,
                                                    side=instruction.side,
                                                    type="LIMIT",
                                                    timeInForce="FOK",
                                                    quantity=instruction.amount,
                                                    price=instruction.price)
            if response["status"] == "EXPIRED":
                self.execution_status = f"FAIL - {len(responses)} steps completed"
                return responses
            responses.append(response)
        else:
            self.execution_status = "PASS"

        return responses

    def _execute_async(self):
        responses = []
        failed_responses = []
        threads = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            for instruction in self.instructions:
                thread = executor.submit(self.bot.client.create_order,
                                         symbol=instruction.symbol,
                                         side=instruction.side,
                                         type="LIMIT",
                                         timeInForce="FOK",
                                         quantity=instruction.amount,
                                         price=instruction.price
                                         )
                threads.append(thread)
        for num, thread in enumerate(threads):
            try:
                response = thread.result()
                response["localTimestamp"] = time.time()
                responses.append(response)
                if response["status"] == "EXPIRED":
                    failed_responses.append(response["symbol"])
            except BinanceAPIException as e:
                if e.code == -2010:
                    failed_action = self.plan.actions[num]
                    failed_asset = failed_action.base if failed_action.side == "SELL" else failed_action.quote
                    msg = f"> *{failed_asset}* balance is too low!"
                    failed_responses.append(failed_action.symbol)
                else:
                    msg = f"_Status_code_: *{e.status_code}*\n" \
                          f"_Code_: *{e.code}*\n" \
                          f"_Message_: *{e.message}*\n"

                hp.send_to_slack(msg, SLACK_KEY, self.bot.slack_group, emoji=':blocky-sweat:')
                if e.status_code == 429: os._exit(1)  # Exit if limit is reached


        # TODO to increase the speed of execution we should get results first and only then analyse them
        if failed_responses:
            self.execution_status = "MISSED"
            self.execution_msg = f"MISSED: {', '.join(failed_responses)}"
        else:
            self.execution_status = self.execution_msg = "PASS"
        self.success_ratio = (len(self.instructions)-len(failed_responses)) / len(self.instructions)

        return responses

    def review_execution(self, responses):
        # Fee is from trade simulation. Calculating new one would require additional BNB books and produce
        # almost if not the same result.

        def rebalance(asset, qnt):
            if asset not in wallet.keys():
                wallet[asset] = qnt
            else:
                wallet[asset] += qnt

        fees = self.success_ratio * self.fees
        wallet = {}
        orders_fills = {'BUY': {}, 'SELL': {}}
        for order in responses:
            action = [action for action in self.plan.actions if action.symbol == order["symbol"]][0]  # TODO Improve this
            if order['side'] == 'BUY':
                money_out = sum([float(fill['price']) * float(fill['qty']) for fill in order['fills']])
                asset_out = action.quote
                money_in = float(order['executedQty'])
                asset_in = action.base
            else:
                money_out = float(order['executedQty'])
                asset_out = action.base
                money_in = sum([float(fill['price']) * float(fill['qty']) for fill in order['fills']])
                asset_in = action.quote

            # Get prices
            fills = [(fill['price'], fill['qty']) for fill in order['fills']]
            orders_fills[order['side']][order['symbol']] = fills
            rebalance(asset_out, -money_out)
            rebalance(asset_in, money_in)

        norm_wallet = self.normalize_wallet(wallet, self.plan.home_asset)
        rebalance("BNB", -fees)

        return {'end_wallet': norm_wallet, 'fills': orders_fills, 'balance': sum(norm_wallet.values())}

    def log_responses(self, responses):
        responses_rows = []
        for response in responses:
            response["id"] = hash(str(response["orderId"]) + response["symbol"] + PLATFORM)
            response["exchangeTimestamp"] = response["transactTime"] / 10 ** 3
            response["exchange"] = PLATFORM
            response["opportunityId"] = self.id
            del response["clientOrderId"]
            del response["transactTime"]
            del response["orderListId"]
            del response["cummulativeQuoteQty"]
            responses_rows.append(response)
        errors = hp.append_rows(rows=responses_rows, dataset="bullseye", table="trades")
        if errors:
            raise Exception(errors)

    def log_opportunity(self):
        opportunity = {
            "id": self.id,
            "foundAtTimestamp": self.timestamp,
            "startAmount": self.plan.start_amount,
            "startCurrency": self.plan.home_asset,
            "estimatedProfitAmount": round(self.final_balance - self.fees, 9),
            "estimatedProfitCurrency": self.plan.profit_asset,
            "estimatedFeeAmount": round(self.fees, 9),
            "estimatedFeeCurrency": self.plan.fee_asset,
            "strategyType": self.plan.strategy,
            "botId": self.plan.instance_id
        }
        errors = hp.append_rows(rows=[opportunity], dataset="bullseye", table="opportunities")
        if errors:
            raise Exception(errors)

    def log_books(self):
        books = self.bot.process_books
        books_rows = []
        for symbol, book in books.items():
            book_row = {
                "id": hash(str(book["lastUpdateId"]) + symbol + "BINANCE"),
                "receivedAtTimestamp": book["timestamp"],
                "opportunityId": self.id,
                "exchange": PLATFORM,
                "symbol": symbol,
                "bids": [{"price": order[0], "qty": order[1]} for order in book["bids"]],
                "asks": [{"price": order[0], "qty": order[1]} for order in book["asks"]]
            }
            books_rows.append(book_row)
        errors = hp.append_rows(rows=books_rows, dataset="bullseye", table="books")
        if errors:
            raise Exception(errors)


class Plan:

    def __init__(self, path, home_asset, start_amount, symbols_info, instance_id, strategy, profit_asset, fee_asset):
        self.path = path
        self.home_asset = home_asset
        self.start_amount = start_amount
        self.instance_id = instance_id
        self.strategy = strategy
        self.actions = self._get_actions(symbols_info)
        self.profit_asset = profit_asset
        self.fee_asset = fee_asset

    def _get_actions(self, symbols_info):
        Action = namedtuple("Action", "symbol side quote base decimals exchange")

        current_asset = self.home_asset
        actions = []
        for market in self.path:
            base = symbols_info[market["symbol"]]["base"]
            quote = symbols_info[market["symbol"]]["quote"]
            sell = base == current_asset
            buy = quote == current_asset
            if (buy or sell) and not (buy and sell):
                side = "BUY" if buy else "SELL"
                current_asset = base if buy else quote
            else:
                raise Exception("Invalid chain.")

            actions.append(Action(symbol=market["symbol"],
                                  side=side,
                                  quote=quote,
                                  base=base,
                                  decimals=symbols_info[market["symbol"]]["decimals"],
                                  exchange=market["exchange"]))
        self.path = [market["symbol"] for market in self.path]

        return actions
