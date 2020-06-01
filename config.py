import os
from dotenv import load_dotenv


load_dotenv()  # Loads env vars from .env file

OPPORTUNITIES_SOURCE = "data/opportunities.json"
RESPONSES_SOURCE = "data/responses.json"
BOOKS_SOURCE = "data/books.json"
RECENT_TRADES_SOURCE = "data/recent_trades.json"

BINANCE_PUBLIC = os.getenv("BINANCE_KEY")
BINANCE_SECRET = os.getenv("BINANCE_SECRET")
SLACK_KEY = os.getenv("SLACK_KEY")
SLACK_GROUP_TEST = "UHN9J9DLG"
SLACK_GROUP = "bullseye"

FEE = 0.00075
