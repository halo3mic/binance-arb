"""Module for testing the Binance bot"""


import json
import argparse

from main import main
from config import DEPLOYMENT_SETTINGS_SOURCE


parser = argparse.ArgumentParser()
parser.add_argument('--plan', default=-1, type=int)
parser.add_argument('--execute', action='store_true')
parser.add_argument('--loop', action='store_true')
parser.add_argument('--main', action='store_true')
args = parser.parse_args()

with open(DEPLOYMENT_SETTINGS_SOURCE) as ds_file:
    deployment_settings = json.load(ds_file)
all_plans = deployment_settings["plans"]
plans = [plan for plan in all_plans if plan["plan_no"] == args.plan or args.plan == -1]
if not plans:
    raise Exception(f"No plan with number {args.plan}")
deployment_settings["plans"] = plans

main(deployment_settings, execute=args.execute, loop=args.loop, test_it=not args.main)
