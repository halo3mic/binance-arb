from urllib.parse import urlencode

from helpers import make_request, make_signature


class BinanceAPI:

    def __init__(self, api_key, secret_key):
        self.api_key = api_key
        self.secret_key = secret_key
        self.spot_base_endpoint = "https://api.binance.com"

    def fetch_server_time(self):
        endpoint = self.spot_base_endpoint + "/api/v3/time"
        response =  make_request(endpoint)
        return response['serverTime']

    def fetch_order_book(self, symbol, limit=100):
        endpoint = self.spot_base_endpoint + '/api/v1/depth'
        params = {'symbol': symbol,
                  'limit': limit
                 }
        headers = {"X-MBX-APIKEY": self.api_key}
        return make_request(endpoint, query=params, headers=headers)

    def fetch_account_info(self, recvWindow=5000):
        endpoint = self.spot_base_endpoint + "/api/v3/account"
        params = {'timestamp': self.fetch_server_time(),
                  'recvWindow': recvWindow,
                 }
        query_string = urlencode(params)
        signature = make_signature(query_string, self.secret_key)
        params['signature'] = signature
        headers = {"X-MBX-APIKEY": self.api_key}
        return make_request(endpoint, query=params, headers=headers)

    def submit_market_order(self, symbol, side, quantity, recvWindow=10000):
        endpoint = self.spot_base_endpoint + "/api/v3/order"
        params = {'symbol': symbol,
                  'side': side,
                  'quantity': quantity,
                  'type': 'MARKET',
                  'recvWindow': recvWindow,
                  'timestamp': self.fetch_server_time()
                 }
        query_string = urlencode(params)
        signature = make_signature(query_string, self.secret_key)
        params['signature'] = signature
        headers = {"X-MBX-APIKEY": self.api_key}
        return make_request(endpoint, query=params, headers=headers, method='POST')


if __name__ == '__main__':
    from dotenv import load_dotenv
    import os


    load_dotenv()
    SECRET_KEY = os.getenv('BINANCE_SECRET')
    API_KEY = os.getenv('BINANCE_KEY')
    ba = BinanceAPI(API_KEY, SECRET_KEY)
    # print(ba.submit_market_order("ETHUSDT", "BUY", 0.05739))
    # print(ba.submit_market_order('ETHEUR', 'SELL', 0.05734))
    # print(ba.submit_market_order('EURUSDT', 'SELL', 11.17))