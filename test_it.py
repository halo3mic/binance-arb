from binance_bot import BinanceBot
import helpers as hp
from config import SLACK_KEY, SLACK_GROUP_TEST


# make chains a namedtuple object with chains, base and amount
chains_xrp = [["XRPUSDT", "XRPEUR", "EURUSDT"],
              ["EURUSDT", "XRPEUR", "XRPUSDT"]]
chains_btc = [["BTCUSDT", "BTCEUR", "EURUSDT"],
              ["EURUSDT", "BTCEUR", "BTCUSDT"]]
chains_eth = [["ETHUSDT", "ETHEUR", "EURUSDT"],
              ["EURUSDT", "ETHEUR", "ETHUSDT"]]
chains_bnb = [["BNBUSDT", "BNBEUR", "EURUSDT"],
              ["EURUSDT", "BNBEUR", "BNBUSDT"]]
base = "USDT"
start_amount = 12

try:
    # make threads for each of the bot instance
    bb = BinanceBot(chains_btc, base, start_amount, execute=0, test_it=1)
    bb.start_listening()
except Exception as e:
    hp.send_to_slack(str(repr(e)), SLACK_KEY, SLACK_GROUP_TEST, emoji=":blocky-grin:")
