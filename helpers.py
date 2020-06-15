import os
import requests
import hmac, hashlib
import json
from sys import platform
from google.cloud import bigquery
from dotenv import load_dotenv

from exceptions import BinanceAPIError


load_dotenv()  # Load env variables - GOOGLE_APPLICATION_CREDENTIALS are required
if (platform == "linux" or platform == "linux2") and (os.getenv("GOOGLE_APPLICATION_CREDENTIALS").startswith("C:")):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_LINUX")
client = bigquery.Client(project='blocklytics-data')


def make_request(path, query=None, headers=None, method='GET'):
    if method == 'GET':    
        response = requests.get(path, query, headers=headers)
    else:
        response = requests.post(path, query, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        raise BinanceAPIError(status_code=response.status_code, data=response)


def make_signature(query_string, secret_key):
    inter = hmac.new(secret_key.encode('utf-8'), digestmod=hashlib.sha256)
    inter.update(query_string.encode('utf-8'))
    signature = inter.hexdigest()
    return signature


def send_to_slack(msg, api_key, channel, emoji=':blocky-money:'):
    # Sending a slack message to the telegram-bot chat-room
    params = {'token': api_key,
              'channel': channel,
              'text': msg,
              'icon_emoji': emoji,
              'username': 'Binance Bot',
              'pretty': 1}
    url = 'https://slack.com/api/chat.postMessage'
    make_request(url, query=params, method='POST')


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
    if not rows:
        return
    table_ref = client.dataset(dataset).table(table)
    job_config = bigquery.QueryJobConfig()
    job_config.destination = table_ref
    job_config.write_disposition = bigquery.WriteDisposition.WRITE_APPEND
    table = client.get_table(table_ref)  # API request
    errors = client.insert_rows(table, rows)  # API request

    return errors


def fetch_symbols_info(path):
    # TODO Fetch these info directly from API - make a function that initializes the bot
    # TODO Dont do this for each path seperatly --> way too slow
    with open(path) as exchange_info_file:
        exchange_info = json.load(exchange_info_file)

    return exchange_info

