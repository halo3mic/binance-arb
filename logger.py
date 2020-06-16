from binance.client import Client, BinanceAPIException
from binance.websockets import BinanceSocketManager
import time

import helpers as hp
from config import *


EXCHANGE = "BINANCE"
TIME_LIMIT = 3600  # 1 hour
SOCKET = None

# TODO make it a class
def process_message(msg):
    if msg['e'] == 'error':
        hp.send_to_slack(msg["m"], SLACK_KEY, SLACK_GROUP, emoji=':blocky-sweat:')
    elif msg["e"] == "outboundAccountInfo":
        print(f"Change in balance found at {time.time()}")
        log_account_balance(msg)


def log_account_balance(account_info_raw):
    """Log account balance in markets where amount is greater than zero."""
    account_info = {
        "id": BINANCE_PUBLIC,  # Unique account identifier - changes with new API
        "exchange": EXCHANGE,
        "timestamp": time.time(),  # Timestamp of the upload time
        "balances": []  # List of individual accounts balances
    }
    account_info["balances"] = [{"symbol": balance["a"], "amount": float(balance["f"])}
                                for balance in account_info_raw["B"]
                                if float(balance["f"]) > 0
                                ]
    rows = [account_info]
    from pprint import pprint

    pprint(rows)
    errors = hp.append_rows(rows=rows, dataset="bullseye", table="balances")
    if errors:
        hp.send_to_slack(str(errors), SLACK_KEY, SLACK_GROUP, emoji=':blocky-sweat:')


def start_logger(client_):
    global SOCKET, start_time
    if SOCKET:
        SOCKET.close()
    start_time = time.time()
    socket_ = BinanceSocketManager(client_)
    socket_.start_user_socket(process_message)
    socket_.start()
    SOCKET = socket_
    print("Listening for account balance updates ...")


if __name__ == "__main__":
    CLIENT = Client(api_key=BINANCE_PUBLIC, api_secret=BINANCE_SECRET)
    start_time = time.time()
    start_logger(CLIENT)
    while 1:
        if time.time() - start_time > TIME_LIMIT:
            start_logger(CLIENT)
            hp.send_to_slack("Logger restarted", SLACK_KEY, SLACK_GROUP, emoji=':blocky-angel:')
        time.sleep(1200)  # Sleep for 20min to save the CPU

