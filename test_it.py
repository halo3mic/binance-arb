import json

from binance_bot import BinanceBot, Plan
from config import EXCHANGE_INFO_SOURCE, DEPLOYMENT_SETTINGS_SOURCE
import helpers as hp


PLAN_NO = float(input())


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
                          strategy="TEST"))

    bb = BinanceBot(plans, execute=1, test_it=1, loop=0, settings=settings["global_settings"])
    bb.start_listening()


if __name__ == "__main__":
    with open(DEPLOYMENT_SETTINGS_SOURCE) as ds_file:
        deployment_settings = json.load(ds_file)

    all_plans = deployment_settings["plans"]
    deployment_settings["plans"] = [plan for plan in all_plans if plan["plan_no"] == PLAN_NO or PLAN_NO == -1]

    main(deployment_settings)
