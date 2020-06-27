from binance.client import Client 
from pprint import pprint
from math import floor, log10
import time

from config import *
from helpers import append_rows


BOTTOM_LIMIT = 36*0.0011
MIN_TRADING_AMOUNT = 0.0011  # In normalizing asset
NORMALIZING_ASSET = "BTC"
CONNECTIONS = {'BNB': ['BTC', 'EUR', 'ETH', 'XRP', 'RUB', 'USDT'],
               'BTC': ['EUR', 'ETH', 'XRP', 'RUB', 'BNB', 'USDT'],
               'ETH': ['BTC', 'EUR', 'XRP', 'RUB', 'BNB', 'USDT'],
               'EUR': ['BTC', 'ETH', 'XRP', 'RUB', 'BNB', 'USDT'],
               'RUB': ['BTC', 'EUR', 'ETH', 'XRP', 'BNB', 'USDT'],
               'USDT': ['BTC', 'EUR', 'ETH', 'XRP', 'RUB', 'BNB'],
               'XRP': ['BTC', 'EUR', 'ETH', 'RUB', 'BNB', 'USDT']}


def get_account_balances(client_):
    "Return account balance in markets where amount is greater than zero."
    account_info_raw = client_.get_account() # Fetch account data
    balances =  dict([(balance["asset"], float(balance["free"])) for balance in account_info_raw["balances"] if float(balance["free"]) > 0])

    return balances

def normalize_balances(balances_, prices_dict_):
    normalized_balances = {}
    for asset, amount in balances_.items():
        _, price = find_assets_price(prices_dict_, asset, NORMALIZING_ASSET)
        normalized_balances[asset] = amount * price 

    return normalized_balances


def find_assets_price(prices_dict_, buy_asset, sell_asset):
    market = None
    str_combo1 = buy_asset + sell_asset
    str_combo2 = sell_asset + buy_asset
    if buy_asset == sell_asset:
        price = 1
    elif str_combo1 in prices_dict_:
        price = float(prices_dict_[str_combo1])
        market = str_combo1
    elif str_combo2 in prices_dict_:
        price = 1 / float(prices_dict_[str_combo2])
        market = str_combo2
    else:
        raise Exception(f"Combination of {buy_asset} and {sell_asset} not listed.")

    return market, price



def get_latest_prices(client_):
    "Return latest binance price for all the available assets."
    prices_raw = client_.get_all_tickers()  # Fetch last traded price for a market
    prices = dict([(market["symbol"], market["price"]) for market in prices_raw])

    return prices


def get_rebalance_instructions(balances_, connections):
    # What amount could an asset possible obtain through direct connections
    get_reach = lambda asset1: sum([balances_[asset2] - BOTTOM_LIMIT for asset2 in connections[asset1] if asset2 in balances_ and balances_[asset2] > (BOTTOM_LIMIT + MIN_TRADING_AMOUNT)])
    # Balances with amounts under the BOTTOM_LIMIT will be regarded as red-balances and others as green-balances
    red_balances = [{"asset": k, "relative_balance": v - BOTTOM_LIMIT, "reach": get_reach(k)} for k, v in balances_.items() if v < BOTTOM_LIMIT]
    green_balances = [{"asset": k, "relative_balance": v - BOTTOM_LIMIT, "reach": get_reach(k)} for k, v in balances_.items() if v > (BOTTOM_LIMIT + MIN_TRADING_AMOUNT)]
    red_balances.sort(key=lambda x: (x["reach"], x["relative_balance"]))

    instructions = []
    for balance in red_balances:
        # print(balance["asset"].center(50, "~"))
        relative_balance = balance["relative_balance"]
        while abs(relative_balance) > MIN_TRADING_AMOUNT:
            # print(f"Relative balance: {relative_balance} (in {balance['asset']})")
            helping_balance = max(green_balances, key=lambda x: x["relative_balance"])
            giving = helping_balance["relative_balance"] if helping_balance["relative_balance"] <= abs(relative_balance) else abs(relative_balance)
            if giving <= MIN_TRADING_AMOUNT:
                break
            # print(f"Giving: {giving} (in {helping_balance['asset']})")
            relative_balance += giving
            helping_asset_index = green_balances.index(helping_balance)
            green_balances[helping_asset_index]["relative_balance"] -= giving
            # print(f"New relative balance: {relative_balance} (in {balance['asset']})")
            instruction = {"sell_asset": helping_balance['asset'], "amount": giving, "buy_asset": balance['asset']}
            instructions.append(instruction)

    return instructions


def denormalize_instructions(instructions_, prices_dict_):
    denormalized_instructions = []
    for instruction in instructions_:
        market, price = find_assets_price(prices_dict_, instruction["buy_asset"], instruction["sell_asset"])
        instruction["market"] = market
        if instruction["sell_asset"] + instruction["buy_asset"] == market:
            instruction["side"] = "SELL"
        else:
            instruction["amount"] /= price 
            instruction["side"] = "BUY"
        denormalized_instructions.append(instruction)

    return denormalized_instructions


def format_instructions(instructions_):
    get_instruction_str = lambda instruction: f"{(instruction['side'] + ' ').ljust(6, '-')} {(str(round_sig(instruction['amount'])) + ' ').ljust(11, '-')} {instruction['market']}"
    instruction_str = "\n".join(get_instruction_str(instruction) for instruction in instructions_)

    return instruction_str


def round_sig(x, sig=4):
    """Return value rounded to specified significant figure"""
    rounded = round(x, sig - floor(log10(abs(x))) - 1)
    rounded = int(rounded) if float(rounded).is_integer() else rounded  # 1.0 --> 1

    return rounded


def execute_instructions(client_, instructions_):
    start_timestamp = time.time()
    responses = []
    for instruction in instructions_:
        if (start_timestamp - time.time() < 1) and len(responses) == 10:
            time.sleep(1)
        r = client_.create_order(symbol=instruction["market"],
                                side=instruction["side"],
                                type="MARKET",
                                quantity=round_sig(instruction["sell_amount"], sig=4)) 
        responses.append(r)

    return r


def main(execute=False):
    client = Client(api_key=BINANCE_PUBLIC, api_secret=BINANCE_SECRET)
    balances = get_account_balances(client)
    prices = get_latest_prices(client)
    normalized_balances = normalize_balances(balances, prices)
    instructions = get_rebalance_instructions(normalized_balances, CONNECTIONS)
    denormalized_instructions = denormalize_instructions(instructions, prices)
    formatted_instructions = format_instructions(denormalized_instructions)
    if execute:
        execute_instructions(client, denormalized_instructions)

    return formatted_instructions
    

if __name__ == "__main__":
    client = Client(api_key=BINANCE_PUBLIC, api_secret=BINANCE_SECRET)
    balances = get_account_balances(client)
    prices = get_latest_prices(client)
    normalized_balances = normalize_balances(balances, prices)
    # pprint(sum(normalized_balances.values()))
    instructions = get_rebalance_instructions(normalized_balances, CONNECTIONS)
    # # pprint(instructions)
    denormalized_instructions = denormalize_instructions(instructions, prices)
    # # pprint(denormalized_instructions)
    formatted_instructions = format_instructions(denormalized_instructions)
    print(formatted_instructions)
    # execute_instructions(client, denormalized_instructions)
