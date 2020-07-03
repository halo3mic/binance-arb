"""Runs the Binance bot."""


import json
import time
import requests
import os

from binance_bot import BinanceBot, Plan
import helpers as hp
from helpers import handle_no_connection
from config import SLACK_KEY, SLACK_GROUP, DEPLOYMENT_SETTINGS_SOURCE


def main(settings, execute=1, test_it=0, loop=1):
    
    @handle_no_connection
    def run_bb_bot(plans):
        bb = BinanceBot(plans, execute=execute, test_it=test_it, loop=loop, settings=settings["global_settings"])
        bb.start_listening()
        hp.send_to_slack(f"Bot instance {id(bb)} started", SLACK_KEY, SLACK_GROUP, emoji=":blocky-robot:")
        timeout = 3600 * 1
        while True:
            time.sleep(timeout)
            delay = time.time() - bb.last_book_update
            msg = f"Bot is alive, last update was {delay} sec ago."
            hp.send_to_slack(msg, SLACK_KEY, SLACK_GROUP, emoji=":blocky-robot:")
            if delay > 60:
                del bb
                raise Exception("Stale books")


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

    run_bb_bot(plans)


if __name__ == "__main__":
    with open(DEPLOYMENT_SETTINGS_SOURCE) as ds_file:
        deployment_settings = json.load(ds_file)

    main(deployment_settings)


