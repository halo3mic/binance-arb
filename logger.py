from binance.client import Client, BinanceAPIException
from binance.websockets import BinanceSocketManager
import time

import helpers as hp
from config import *


EXCHANGE = "BINANCE"


def process_message(msg):
    if msg['e'] == 'error':
        hp.send_to_slack(msg, SLACK_KEY, SLACK_GROUP_TEST, emoji=':blocky-sweat:')  # TODO change to main version 
    elif msg["e"] == "outboundAccountInfo":
        log_account_balance(msg)


def log_account_balance(account_info_raw):
    """Log account balance in markets where amount is greater than zero."""
    account_info = {
        "id": hash(BINANCE_PUBLIC),  # Unique account identifier - changes with new API
        "exchange": EXCHANGE,
        "timestamp": time.time(),  # Timestamp of the upload tim
        "balances": {}  # List of individual accounts balances
    }
    account_info["balances"] = [{"symbol": balance["a"], "amount": float(balance["f"])}
                                for balance in account_info_raw["B"]
                                if float(balance["f"]) > 0
                                ]
    rows = [account_info]
    errors = hp.append_rows(rows=rows, dataset="bullseye", table="balances")
    if errors:
        hp.send_to_slack(errors, SLACK_KEY, SLACK_GROUP_TEST, emoji=':blocky-sweat:')  # TODO change to main version 


if __name__ == "__main__":
    client = Client(api_key=BINANCE_PUBLIC, api_secret=BINANCE_SECRET)
    bm = BinanceSocketManager(client)
    bm.start_user_socket(process_message)
    bm.start()
    print("Listening for account balance updates ...")
