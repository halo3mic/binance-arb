"""Runs the Binance bot."""


import json

from binance_bot import BinanceBot, Plan
import helpers as hp
from config import SLACK_KEY, SLACK_GROUP, DEPLOYMENT_SETTINGS_SOURCE
import time


def main(settings, execute=1, test_it=0, loop=1):
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
    try:
        bb = BinanceBot(plans, execute=execute, test_it=test_it, loop=loop, settings=settings["global_settings"])
        bb.start_listening()
        timeout = 3600 * 4
        while True:
            time.sleep(timeout)
            msg = f"Bot is alive, last update was {time.time() - bb.last_book_update} sec ago."
            hp.send_to_slack(msg, SLACK_KEY, SLACK_GROUP, emoji=":blocky-grin:")
    except Exception as e:
        hp.send_to_slack(str(e), SLACK_KEY, SLACK_GROUP, emoji=":blocky-grin:")
        exit()


if __name__ == "__main__":
    with open(DEPLOYMENT_SETTINGS_SOURCE) as ds_file:
        deployment_settings = json.load(ds_file)

    main(deployment_settings)


