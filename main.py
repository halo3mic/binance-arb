"""Runs the Binance bot."""


import json
import time
import requests
import os

from binance_bot import BinanceBot, Plan
import helpers as hp
from config import SLACK_KEY, SLACK_GROUP, DEPLOYMENT_SETTINGS_SOURCE


def main(settings, execute=1, test_it=0, loop=1):

    def run_bb_bot(plans):
        bb = BinanceBot(plans, execute=execute, test_it=test_it, loop=loop, settings=settings["global_settings"])
        bb.start_listening()
        timeout = 3600 * 4
        while True:
            time.sleep(timeout)
            msg = f"Bot is alive, last update was {time.time() - bb.last_book_update} sec ago."
            hp.send_to_slack(msg, SLACK_KEY, SLACK_GROUP, emoji=":blocky-robot:")

    # deploymentSettings --> plans
    plans = []
    for plan in settings["plans"]:
        plans.append(Plan(market_conds=plan["markets"],
                          start_amount=float(plan["start_amount"]),
                          home_asset=plan["start_currency"],
                          instance_id=settings["instance_id"],
                          strategy="ARBITRAGE",
                          profit_asset=plan["profit_asset"],
                          fee_asset=plan["fee_asset"]))

    while 1:
        try:
            run_bb_bot(plans)  # Runs in an infinite loop
        except Exception as e:
            try:
                hp.send_to_slack(str(e), SLACK_KEY, SLACK_GROUP, emoji=":blocky-grin:")
            except requests.exceptions.ConnectionError:
                timestamp = time.time()
                url = "google.com"  # TODO change to SlackAPI url
                while 1:
                    response = os.system(f"ping {url}")
                    if response == 0:  # If response is a success
                        msg = f"Connection was disturbed for {time.time() - timestamp}"
                        hp.send_to_slack(msg, SLACK_KEY, SLACK_GROUP, emoji=":blocky-grin:")
                        break
                    time.sleep(20)  # Try again in 20 sec


if __name__ == "__main__":
    with open(DEPLOYMENT_SETTINGS_SOURCE) as ds_file:
        deployment_settings = json.load(ds_file)

    main(deployment_settings)


