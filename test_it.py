from dotenv import load_dotenv
import os
import sys

from main import BinanceBot


load_dotenv()
SECRET_KEY = os.getenv('BINANCE_SECRET')
API_KEY = os.getenv('BINANCE_KEY')
SLACK_KEY = os.getenv('SLACK_KEY')
SLACK_MEMBER_ID = os.getenv('SLACK_MEMBER_ID')

chains = [["ETHUSDT", "ETHEUR", "EURUSDT"], 
		  ["EURUSDT", "ETHEUR", "ETHUSDT"]]
bot = BinanceBot(API_KEY, SECRET_KEY, SLACK_KEY, SLACK_MEMBER_ID)
bot.to_slack = 1
bot.execute_trade = 0
bot.filter_off = 1
bot.run_once(chains)


