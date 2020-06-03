from binance_bot import BinanceBot
import helpers as hp
from config import SLACK_KEY, SLACK_GROUP


# TODO make chains a namedtuple object with chains, base and amount
chains_xrp_eur = [["XRPUSDT", "XRPEUR", "EURUSDT"],
                  ["EURUSDT", "XRPEUR", "XRPUSDT"]]
chains_xrp_rub = [["XRPUSDT", "XRPRUB", "USDTRUB"],
                  ["USDTRUB", "XRPRUB", "XRPUSDT"]]
chains_btc_eur = [["BTCUSDT", "BTCEUR", "EURUSDT"],
                  ["EURUSDT", "BTCEUR", "BTCUSDT"]]
chains_btc_rub = [["BTCUSDT", "BTCRUB", "USDTRUB"],
                  ["USDTRUB", "BTCRUB", "BTCUSDT"]]
chains_eth_eur = [["ETHUSDT", "ETHEUR", "EURUSDT"],
                  ["EURUSDT", "ETHEUR", "ETHUSDT"]]
chains_eth_rub = [["ETHUSDT", "ETHRUB", "USDTRUB"],
                  ["USDTRUB", "ETHRUB", "ETHUSDT"]]
chains_bnb_eur = [["BNBUSDT", "BNBEUR", "EURUSDT"],
                  ["EURUSDT", "BNBEUR", "BNBUSDT"]]
chains_bnb_rub = [["BNBUSDT", "BNBRUB", "USDTRUB"],
                  ["USDTRUB", "BNBRUB", "BNBUSDT"]]
base = "USDT"
start_amount = 12

key = input()
commands = {"bnb": chains_bnb_rub + chains_bnb_eur,
            "eth": chains_eth_rub + chains_eth_eur,
            "btc": chains_btc_rub + chains_btc_eur,
            "xrp": chains_xrp_rub + chains_xrp_eur}

try:
    # make threads for each of the bot instance
    bb = BinanceBot(commands[key], base, start_amount, execute=True, test_it=False)
    bb.start_listening()
except Exception as e:
    hp.send_to_slack(str(e), SLACK_KEY, SLACK_GROUP, emoji=":blocky-grin:")
