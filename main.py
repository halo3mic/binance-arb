import json

from binance_bot import BinanceBot, Plan
import helpers as hp
from config import SLACK_KEY, SLACK_GROUP, DEPLOYMENT_SETTINGS_SOURCE, EXCHANGE_INFO_SOURCE


def main(settings):
    # TODO add exchange in json file when plans are saved?
    symbols_info = hp.fetch_symbols_info(EXCHANGE_INFO_SOURCE)

    plans = []
    for plan in settings["plans"]:
        plans.append(Plan(path=plan["markets"],
                          start_amount=float(plan["start_amount"]),
                          home_asset=plan["start_currency"],
                          symbols_info=symbols_info,
                          instance_id=settings["instance_id"],
                          strategy="ARBITRAGE"))
    try:
        bb = BinanceBot(plans, execute=1, test_it=0, loop=1, settings=settings["global_settings"])
        bb.start_listening()
    except Exception as e:
        hp.send_to_slack(str(e), SLACK_KEY, SLACK_GROUP, emoji=":blocky-grin:")


if __name__ == "__main__":
    with open(DEPLOYMENT_SETTINGS_SOURCE) as ds_file:
        deployment_settings = json.load(ds_file)

    main(deployment_settings)

