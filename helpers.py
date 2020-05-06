import requests
import hmac, hashlib

from exceptions import BinanceAPIError


def make_request(path, query={}, headers=None, method='GET'):
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