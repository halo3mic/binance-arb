import os
from urllib.parse import urlencode
from dotenv import load_dotenv
import time

from helpers import make_request, make_signature


API_KEY = os.getenv('BINANCE_KEY')
SECRET_KEY = os.getenv('BINANCE_SECRET')


def fetch_server_time(api_key, base_endpoint="https://api.binance.com"):
    endpoint = base_endpoint + "/api/v3/time"
    response =  make_request(endpoint)
    return response['serverTime']
    

def fetch_account_info(api_key, secret_key, recvWindow=5000, base_endpoint="https://api.binance.com"):
    endpoint = base_endpoint + "/api/v3/account"
    params = {'timestamp': fetch_server_time(API_KEY), 
              'recvWindow': recvWindow,
             }
    query_string = urlencode(params)
    signature = make_signature(query_string, secret_key)
    params['signature'] = signature
    headers = {"X-MBX-APIKEY": api_key}
    return make_request(endpoint, query=params, headers=headers)


def fetch_order_book(api_key, symbol, base_endpoint="https://api.binance.com", limit=100):
    endpoint = base_endpoint + '/api/v1/depth'
    params = {'symbol': symbol,
              'limit': limit
             }
    headers = {"X-MBX-APIKEY": api_key}
    return make_request(endpoint, query=params, headers=headers)


def submit_market_order(symbol, side, quantity, api_key, secret_key, recvWindow=10000, base_endpoint="https://api.binance.com"):
    endpoint = base_endpoint + "/api/v3/order/test"
    params = {'symbol': symbol,
              'side': side,
              'quantity': quantity,
              'type': 'MARKET',
              'recvWindow': recvWindow,
              'timestamp': fetch_server_time(API_KEY)
             }
    query_string = urlencode(params)
    signature = make_signature(query_string, secret_key)
    params['signature'] = signature
    headers = {"X-MBX-APIKEY": api_key}
    return make_request(endpoint, query=params, headers=headers, method='POST')


if __name__ == '__main__':
    from pprint import pprint
    load_dotenv()
    API_KEY = os.getenv('BINANCE_KEY')
    SECRET_KEY = os.getenv('BINANCE_SECRET')
    print(submit_market_order('ETHUSDT', 'BUY', 0.1, API_KEY, SECRET_KEY))