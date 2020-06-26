"""Functions that Binance bot uses, but are not specific for it."""


import os
import requests
import json
from sys import platform
from google.cloud import bigquery
from dotenv import load_dotenv


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
