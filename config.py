import os
from dotenv import load_dotenv


load_dotenv()  # Loads env vars from .env file

SYMBOLS_INFO_SOURCE = "data/symbols_info.json"

BINANCE_PUBLIC = os.getenv("BINANCE_KEY")
BINANCE_SECRET = os.getenv("BINANCE_SECRET")
SLACK_KEY = os.getenv("SLACK_KEY")
SLACK_GROUP_TEST = "UHN9J9DLG"
SLACK_GROUP = "bullseye"

FEE = 0.00075
PLATFORM = "BINANCE"

