import itertools as it
from pprint import pprint
import helpers as hp


POSSIBLE_PAIRS = [
	"BNBEUR",
	"BNBRUB",
	"BNBUSDT",
	"BTCEUR",
	"BTCRUB",
	"BTCUSDT",
	"ETHEUR",
	"ETHRUB",
	"ETHUSDT",
	"EURUSDT",
	"USDTRUB",
	"XRPEUR",
	"XRPRUB",
	"XRPUSDT"
]

symbols_info = hp.fetch_symbols_info()
paths_all = it.permutations(POSSIBLE_PAIRS, 3)

paths_valid = []
for path in paths_all:
	for i in range(len(path)):
		next_index = 0 if i == len(path)-1 else i + 1
		quote = symbols_info[path[i]]["quote"]
		base = symbols_info[path[i]]["base"]
		cond1 =  quote in path[next_index] and quote not in path[i-1]
		cond2 = base in path[next_index] and base not in path[i-1]
		if not (cond1 or cond2):
			break
	else:
		paths_valid.append(path)

pprint(paths_valid)