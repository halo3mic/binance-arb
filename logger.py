"""Save each account balance update that comes through websocket."""


from binance.client import Client
from binance.websockets import BinanceSocketManager
import time

import helpers as hp
from config import *


EXCHANGE = "BINANCE"
USER_TIMEOUT = 40 * 60  # 40 min


def process_message(msg):
    """React to the incoming websocket feed."""
    if msg['e'] == 'error':
        hp.send_to_slack(msg["m"], SLACK_KEY, SLACK_GROUP, emoji=':blocky-sweat:')
    elif msg["e"] == "outboundAccountInfo":
        log_account_balance(msg)


def log_account_balance(account_info_raw):
    """Log account balance in markets where amount is greater than zero."""
    account_info = {"id": BINANCE_PUBLIC,  # Unique account identifier - changes with new API
                    "exchange": EXCHANGE,
                    "timestamp": time.time(),  # Timestamp of the upload time
                    "balances": []  # List of individual accounts balances
    }
    account_info["balances"] = [{"symbol": balance["a"], "amount": float(balance["f"])}
                                for balance in account_info_raw["B"]
                                if float(balance["f"]) > 0
                                ]
    rows = [account_info]

    errors = hp.append_rows(rows=rows, dataset="bullseye", table="balances")
    if errors:
        hp.send_to_slack(str(errors), SLACK_KEY, SLACK_GROUP, emoji=':blocky-sweat:')


def start_logger():
    """Start the websocket."""
    client = Client(api_key=BINANCE_PUBLIC, api_secret=BINANCE_SECRET)
    socket_ = BinanceSocketManager(client, user_timeout=USER_TIMEOUT)
    socket_.start_user_socket(process_message)
    socket_.start()
    print("Listening for account balance updates ...")

    while 1:
        # Ping the exchange that we still want to listen
        time.sleep(USER_TIMEOUT)
        client.stream_keepalive(socket_._listen_keys["user"])


if __name__ == "__main__":
    start_logger()
