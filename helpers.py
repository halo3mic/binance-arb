"""Functions that Binance bot uses, but are not specific for it."""


import os
import requests
import json
import time
from sys import platform
from math import log10, floor
from google.cloud import bigquery
from dotenv import load_dotenv

from config import *


load_dotenv()  # Load env variables - GOOGLE_APPLICATION_CREDENTIALS are required
# Different way of saving for linux and windows
if (platform == "linux" or platform == "linux2") and (os.getenv("GOOGLE_APPLICATION_CREDENTIALS").startswith("C:")):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_LINUX")
client = bigquery.Client(project='blocklytics-data')


def send_to_slack(msg, api_key, channel, emoji=':blocky-money:'):
    # Sending a slack message to the telegram-bot chat-room
    params = {'token': api_key,
              'channel': channel,
              'text': msg,
              'icon_emoji': emoji,
              'username': 'Binance Bot',
              'pretty': 1}
    url = 'https://slack.com/api/chat.postMessage'
    requests.post(url, params)


def round_up(x, m):
    x *= 10**m
    x = int(x) + 1 
    x /= 10**m
    return x


def round_down(x, m):
    x *= 10**m
    x = int(x) 
    x /= 10**m
    return x


def save_json(content, key, filename):
    """Save json file with a new key entry."""
    try:
        with open(filename, 'r') as jsonfile:
            data = json.load(jsonfile)
    except FileNotFoundError:
        data = {}
    with open(filename, 'w') as jsonfile:
        if key in data.keys():
            raise Exception("Overwritting!")
        data[key] = content
        json.dump(data, jsonfile, indent=4)


def get_avg(elements):
    return sum([element[0] * element[1] for element in elements]) / sum([element[1] for element in elements])


def append_rows(dataset, table, rows):
    """Append rows to BigQuery table."""
    if not rows:
        return
    table_ref = client.dataset(dataset).table(table)
    job_config = bigquery.QueryJobConfig()
    job_config.destination = table_ref
    job_config.write_disposition = bigquery.WriteDisposition.WRITE_APPEND
    table = client.get_table(table_ref)  # API request
    errors = client.insert_rows(table, rows)  # API request

    return errors

def handle_no_connection(fun):
    """Restart a function if there is an error and report it to slack. If no connection, wait till it is re-established"""
    
    def wrapper(*args, **kwargs):
        while 1:
            try:
                fun(*args, **kwargs)
            except Exception as e:
                try:
                    send_to_slack(str(e), SLACK_KEY, SLACK_GROUP, emoji=":blocky-grin:")
                except requests.exceptions.ConnectionError:
                    timestamp = time.time()
                    url = "google.com"  # TODO change to SlackAPI url
                    while 1:
                        response = os.system(f"ping -c 1 {url}")
                        if response == 0:  # If response is a success
                            msg = f"Connection was disturbed for {time.time() - timestamp}"
                            send_to_slack(msg, SLACK_KEY, SLACK_GROUP, emoji=":blocky-grin:")
                            break
                        time.sleep(20)  # Try again in 20 sec

    return wrapper

def round_sig(x, sig=4, precision=8):
    """Return value rounded to specified significant figure"""
    rounded = round(x, sig - floor(log10(abs(x))) - 1)
    rounded = int(rounded) if float(rounded).is_integer() else rounded  # 1.0 --> 1
    rounded_str = format(rounded, f".{precision}f").rstrip(".0")
    
    return rounded_str