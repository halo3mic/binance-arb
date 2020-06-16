import json

from binance_bot import BinanceBot, Plan
import helpers as hp
from config import SLACK_KEY, SLACK_GROUP, DEPLOYMENT_SETTINGS_SOURCE, EXCHANGE_INFO_SOURCE
import time


def main(settings):
    symbols_info = hp.fetch_symbols_info(EXCHANGE_INFO_SOURCE)

    plans = []
    for plan in settings["plans"]:
        plans.append(Plan(path=plan["markets"],
                          start_amount=float(plan["start_amount"]),
                          home_asset=plan["start_currency"],
                          symbols_info=symbols_info,
                          instance_id=settings["instance_id"],
                          strategy="ARBITRAGE",
                          profit_asset=plan["profit_asset"],
                          fee_asset=plan["fee_asset"]))
    try:
        bb = BinanceBot(plans, execute=1, test_it=0, loop=1, settings=settings["global_settings"])
        bb.start_listening()
        limit = 60
        while 1:
            update1 = bb.last_book_update
            time.sleep(limit)
            if update1 == bb.last_book_update:
                msg = f"No book update for more than {limit} sec."
                hp.send_to_slack(msg, SLACK_KEY, SLACK_GROUP, emoji=':blocky-sweat:')
                # Restart the bot
                bb.close()
                bb.start_listening()
                hp.send_to_slack("Bot restarted", SLACK_KEY, SLACK_GROUP, emoji=':blocky-angel:')

    except Exception as e:
        hp.send_to_slack(str(e), SLACK_KEY, SLACK_GROUP, emoji=":blocky-grin:")
        exit()


if __name__ == "__main__":
    with open(DEPLOYMENT_SETTINGS_SOURCE) as ds_file:
        deployment_settings = json.load(ds_file)

    main(deployment_settings)

