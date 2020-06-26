"""Heart of the Binance bot."""


from binance.client import Client, BinanceAPIException
from binance.websockets import BinanceSocketManager
from threading import Thread
from twisted.internet import reactor
from collections import namedtuple
import time
import concurrent.futures  # For threading and multiprocessing
import re
import atexit

import helpers as hp
from config import *  # Settings are stored here
import rebalance
import traceback


class BinanceBot(BinanceSocketManager):

    def __init__(self, plans, execute=True, test_it=False, loop=True, settings=None):
        self.slack_group = SLACK_GROUP if not test_it else SLACK_GROUP_TEST
        # TODO Add keys to the settings 
        self.client = Client(api_key=BINANCE_PUBLIC, api_secret=BINANCE_SECRET)

        self.execute = execute  # If false no opportunity gets executed
        self.test_it = test_it  # Opportunity gets executed even if unprofitable
        self.loop = loop  # If false it will only check one book update
        self.busy = False  # Is the bot currently handling one of the books
        self.plans = plans

        self.plan_markets = {market for plan in plans for market in plan.path}  # All markets that will be checked by the instance
        self.books = {}  # Latest books 
        self.process_books = {}  # Books that will be processed 
        self.last_book_update = None  # Timestamp of the last book update
        self.exceptions = []  # Store exceptions from all threads here

        BinanceSocketManager.__init__(self, self.client)

    def handle_message(self, msg):
        """React to the book update."""
        if msg.get("e") == 'error':
            hp.send_to_slack(str(msg), SLACK_KEY, SLACK_GROUP, emoji=':blocky-sweat:')
        pair = re.findall(r"^[a-z]*", msg["stream"])[0].upper()  # Find out for which market was the book update
        self.books[pair] = msg["data"]  # Save new books (and overwrite the old ones)
        self.last_book_update = self.books[pair]["timestamp"] = time.time()

        # If not busy and all assets books are available
        if not self.busy and len(self.books) == len(self.plan_markets):
            self.busy = True  # Acts as a lock 
            self.process_books = self.books.copy()  # Makes sure these books won't be overwritten while processing
            Thread(target=self.process_plans, args=(pair,)).start()

        if self.exceptions:
            # Take all the exceptions from threads and message them to Slack group
            msg = " >" + "\n".join([str(exc) for exc in self.exceptions])
            self.exceptions = []
            hp.send_to_slack(msg, SLACK_KEY, self.slack_group, emoji=':blocky-money:')

    def process_plans(self, pair):
        """Check if book updates produced profitable opportunities and act if so."""
        try:
            valid_plans = [plan for plan in self.plans if pair in plan.path]  # Only proccess plans which include updated market

            for plan in valid_plans:
                opportunity = Opportunity(self, plan)
                opportunity.find_opportunity()
                if opportunity.profit > 0 or (self.test_it and plan == valid_plans[-1]):
                    # Save used books before releasing the lock, so they dont get overwritten
                    used_markets = {market for plan in valid_plans for market in plan.path}
                    used_books = dict([(market, book) for market, book in self.process_books.items()
                                       if market in used_markets])
                    if self.execute:
                        responses = opportunity.execute(async_=True)
                        opportunity.actual_profit = format(opportunity.review_execution(responses)["balance"], ".8f") + " " + opportunity.plan.home_asset
                        opportunity.log_responses(responses)
                    # Log data even if execution is turned off
                    opportunity.log_opportunity()
                    opportunity.log_books(used_books)
                    opportunity.to_slack()

        except Exception as e:
            e_str = traceback.format_exc()
            self.exceptions.append(e_str)
        finally:
            # Release the lock if even if exception was raised
            self.busy = False if self.loop else True

    def start_listening(self):
        """Start the websocket."""
        stream_names = [pair.lower() + "@depth10@100ms" for pair in self.plan_markets]
        self.start_multiplex_socket(stream_names, self.handle_message)
        if not reactor.running: self.start()  # Start the reactor if not running (for the restart)
        atexit.register(self.upon_closure)  # Close the sockets when you close the terminal
        self.books = self.get_intial_books(self.plan_markets)  # Get initial books
        self.last_book_update = time.time()

    def upon_closure(self):
        """Exit the thread and stop the reactor when the bot stops."""
        self.close()
        if reactor.running: reactor.stop()
        print("GOODBYE!")

    def get_intial_books(self, pairs):
        """Return the initial books for all markets via REST API calls."""
        print("Fetching initial books".center(80, "~"))
        t1 = time.time()
        books = {}
        counter = 0
        for pair in pairs:
            print(f"{pair} fetched!")
            books[pair] = self.client.get_order_book(symbol=pair)
            books[pair]["timestamp"] = time.time()
            # If there were 5 API calls in less than a second wait a second before continuing
            if counter == 5 and (time.time()-t1 < 1):
                time.sleep(1)
                counter = 0
                t1 = time.time()
            else:
                counter += 1
        print(f"Finished! Time taken: {time.time() - t1} sec.")
        os.system("clear")

        return books


class Opportunity:
    """Plan with the current markets' books."""

    def __init__(self, bot, plan):
        self.bot = bot  # Instance of the bot
        self.plan = plan  # Opportunity's plan

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
        # TODO Improve the id generation method
        self.id = f"{str(int(self.timestamp*1000))}-{str(hash(str([action.symbol for action in plan.actions])))[-4:]}"

    def find_opportunity(self):
        """Find if plan is profitable based on current order books."""
        results = self.simulate_trade(self.plan.actions, self.plan.start_amount, self.plan.home_asset, FEE)
        norm_wallet = self.normalize_wallet(results["wallet"], self.plan.home_asset)  # Convert all remaining assets to normalizing asset
        norm_fees = self.normalize_wallet(results["fees"], self.plan.home_asset)  # Convert all fee assets into normalizing asset
        final_balance = sum(norm_wallet.values())  # Final balance, without the fees

        self.instructions = results["instructions"]
        self.final_balance = final_balance
        self.fees = sum(norm_fees.values())
        self.profit = self.final_balance - self.plan.start_amount - self.fees

    def simulate_trade(self, actions, starting_amount, start_asset, fee):
        """Simulate plan execution with the current order books and return the results."""

        def rebalance_wallet(wallet_, asset, qnt):
            """Add the asset amount to the wallet and return rebalanced wallet."""
            if asset not in wallet_.keys():
                wallet_[asset] = qnt
            else:
                wallet_[asset] += qnt

            return wallet_

        Instruction = namedtuple("Instruction", "price amount side symbol")
        instructions = []
        wallet = {start_asset: starting_amount}
        fees = {}  # Separate wallet for the fees
        holding = starting_amount

        for action in actions:
            side = {"BUY": "asks", "SELL": "bids"}[action.side]

            if action.side == 'BUY':
                best_orders, price = self.market_price(action.symbol, side, holding, inverse=True)
                # If multiple orders with different prices fill our action then select the one with the lowest price
                # This works because the the platform looks for order with specified price or better one
                worst_price = max(best_orders, key=lambda x: x[0])[0]
                money_in_full = holding * price  # Amount before the qnt_filter is applied
                money_in = self.apply_qnt_filter(money_in_full, action)  # Rounds to the allowed decimal place for the market
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
            # Rebalance the wallets
            wallet = rebalance_wallet(wallet, asset_out, -money_out)
            wallet = rebalance_wallet(wallet, asset_in, money_in)
            fees = rebalance_wallet(fees, asset_in, money_in * fee)
            holding = money_in

        return {"wallet": wallet, "fees": fees, "instructions": instructions}

    def normalize_wallet(self, wallet_, normalizing_to):
        """Return wallet in which all assets are normalized to one normalizing asset."""
        norm_wallet = wallet_
        for asset in wallet_:
            if asset == normalizing_to or wallet_[asset] == 0: continue
            # TODO Find a better, smoother way of doing the below
            if asset + normalizing_to in self.bot.plan_markets:
                pair = asset + normalizing_to
                inverse = False
            else:
                pair = normalizing_to + asset
                inverse = True
            side = "asks" if inverse else "bids"
            _, price = self.market_price(pair, side, wallet_[asset], inverse=inverse)  # TODO It is not always "bids"
            norm_wallet[asset] = wallet_[asset] * price

        return norm_wallet

    def market_price(self, pair, side, amount, inverse=False):
        """Returns the best price for the action and amount."""
        if pair not in self.bot.process_books:
            raise Exception(f"Pair {pair} not in the books.")
        orders = self.bot.process_books[pair][side]
        return self.get_best_orders(orders, amount, inverse=inverse)

    def apply_qnt_filter(self, qnt, action, round_type='down'):
        """Return the amount rounded based on market decimal limit."""
        rounding = {'even': round, 'up': hp.round_up, 'down': hp.round_down}
        rounded = rounding[round_type](float(qnt), action.decimals)
        return rounded

    @staticmethod
    def get_best_orders(orders, money_in, inverse=False):
        """Return best orders and overall price for the orders and input-amount."""
        avl = money_in
        money_out = []  # Best orders (price, amount)
        for price, amount in orders:
            price, amount = float(price), float(amount)
            diff = avl - (amount if not inverse else amount * price)
            if diff <= 0:
                remaining = avl if not inverse else avl / price
                money_out.append((price, remaining))
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
        # If inverse then return inversed price, but NOT inversed orders
        return money_out, price

    def to_slack(self):
        """Send opportunity to Slack."""
        if self.execution_status != "PASS":
            self.actual_profit = f"*{self.actual_profit}"
        action_separator = " | " if self._async else " > "
        msg = f"_Opportunity ID:_ *{self.id}*\n" \
              f"_Action:_ *{action_separator.join([(step.symbol + '-' + step.side) for step in self.plan.actions])}*\n" \
              f"_EstimatedProfit:_ *{self.profit:.8f} {self.plan.home_asset}*\n" \
              f"_ActualProfit:_ * {self.actual_profit}*\n" \
              f"_OrdersExecution time:_ *{self.execution_time}*\n" \
              f"_Status_: *{self.execution_status}*\n" \
              f"_Execution msg_: *{self.execution_msg}*\n" \
              f"_Start amount:_ *{self.plan.start_amount} {self.plan.home_asset}*\n"
        hp.send_to_slack(msg, SLACK_KEY, self.bot.slack_group, emoji=':blocky-money:')

    def execute(self, async_=False):
        """Execute the opportunity and return the response."""
        self._async = async_
        start_time = time.perf_counter_ns()
        responses = self._execute_async() if async_ else self._execute_sync()
        if not responses:
            return None
        self.execution_time = str(time.perf_counter_ns() - start_time)[:-6] + " ms"
        
        return responses

    def _execute_sync(self):
        """Execute opportunity synchronously."""
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
        """Execute an opportunity asynchronously."""
        self.execution_status = "PASS"
        success_message = "| "
        responses = []
        threads = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            for instruction in self.instructions:
                thread = executor.submit(self.bot.client.create_order,
                                         symbol=instruction.symbol,
                                         side=instruction.side,
                                         type="LIMIT",
                                         timeInForce="IOC",
                                         quantity=instruction.amount,
                                         price=instruction.price
                                         )
                threads.append(thread)

            for num, thread in enumerate(threads):
                try:
                    response = thread.result()
                    response["localTimestamp"] = time.time()
                    responses.append(response)
                except BinanceAPIException as e:
                    executor.shutdown(wait=True)  # Wait for all the threads to execute
                    self.bot.busy = False if self.bot.loop else True  # Release the lock as soon as the execution is finished

                    if e.code == -2010:
                        failed_action = self.plan.actions[num]
                        failed_asset = failed_action.base if failed_action.side == "SELL" else failed_action.quote
                        msg = f"> *{failed_asset}* balance is too low!"
                        msg += f"\n```{rebalance.main()}```"
                        self.execution_status = "MISSED"
                        success_message += f"{failed_action.symbol} 0% | "
                    else:
                        msg = f"_Status_code_: *{e.status_code}*\n" \
                              f"_Code_: *{e.code}*\n" \
                              f"_Message_: *{e.message}*\n"
                    hp.send_to_slack(msg, SLACK_KEY, self.bot.slack_group, emoji=':blocky-sweat:')
                    if e.status_code == 429: os._exit(1)  # Exit if limit is reached
                    break  # Stop wasting the resources and time if whole opporunity won't be filled
            else:
                self.bot.busy = False if self.bot.loop else True  # Release the lock as soon as the execution is finished

            executor.shutdown(wait=True)  # Wait for all the threads to execute

        self.success_ratio = 0
        for response in responses:
            if response["status"] != "FILLED":
                self.execution_status = "MISSED"
            success_rate = float(response["executedQty"]) / float(response["origQty"])
            self.success_ratio += success_rate
            success_message += f"{response['symbol']} {success_rate:.0%} | "
        self.execution_msg = success_message
        self.success_ratio /= len(self.instructions)

        return responses

    def review_execution(self, responses):
        """Simulate the execution with the execution-response."""
        # Fee is from trade simulation. Calculating new one would require additional BNB books and produce
        # almost if not the same result.

        def rebalance_wallet(wallet_, asset, qnt):
            """Add the asset amount to the wallet and return rebalanced wallet."""
            if asset not in wallet_.keys():
                wallet_[asset] = qnt
            else:
                wallet_[asset] += qnt

            return wallet_

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
            wallet = rebalance_wallet(wallet, asset_out, -money_out)
            wallet = rebalance_wallet(wallet, asset_in, money_in)

        norm_wallet = self.normalize_wallet(wallet, self.plan.home_asset)
        norm_wallet = rebalance_wallet(norm_wallet, "BNB", -fees)

        return {'end_wallet': norm_wallet, 'fills': orders_fills, 'balance': sum(norm_wallet.values())}

    def log_responses(self, responses):
        """Log execution reponses to BigQuery."""
        responses_rows = []
        for response in responses:
            response["id"] = hash(str(response["orderId"]) + response["symbol"] + PLATFORM)
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
        """Log opportunity to BigQuery."""
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

    def log_books(self, books):
        """Log books to BigQuery"""
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
    """Procedure and conditions in which actions should execute, no matter the order book."""

    def __init__(self, market_conds, home_asset, start_amount, instance_id, strategy, profit_asset, fee_asset):
        self.path = [market_cond["symbol"] for market_cond in market_conds]
        self.home_asset = home_asset  # Start and end asset
        self.start_amount = start_amount
        self.instance_id = instance_id
        self.strategy = strategy
        self.actions = self._get_actions(market_conds)
        self.profit_asset = profit_asset  # Asset in which profit should be logged
        self.fee_asset = fee_asset  # Asset in which fees should be logged

    def _get_actions(self, plan):
        """Return list of actions."""
        # Action is execution condition for a market
        Action = namedtuple("Action", "symbol side quote base decimals exchange")

        current_asset = self.home_asset
        actions = []
        for market_cond in plan:
            base = market_cond["base"]
            quote = market_cond["quote"]
            sell = base == current_asset
            buy = quote == current_asset
            if (buy or sell) and not (buy and sell):
                side = "BUY" if buy else "SELL"
                current_asset = base if buy else quote
            else:
                raise Exception("Invalid chain.")

            actions.append(Action(symbol=market_cond["symbol"],
                                  side=side,
                                  quote=quote,
                                  base=base,
                                  decimals=market_cond["decimals"],
                                  exchange=market_cond["exchange"]))

        return actions
