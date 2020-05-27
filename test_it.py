from binance_bot import BinanceBot
import helpers as hp
from config import SLACK_GROUP, SLACK_KEY


# make chains a namedtuple object with chains, base and amount
chains = [["XRPUSDT", "XRPEUR", "EURUSDT"],
          ["EURUSDT", "XRPEUR", "XRPUSDT"]]
base = "USDT"
start_amount = 12

try:
    # make threads for each of the bot instance
    bb = BinanceBot(chains, base, start_amount, execute=0, test_it=1)
    bb.start_listening()
except Exception as e:
    hp.send_to_slack(str(e), SLACK_GROUP, SLACK_KEY)