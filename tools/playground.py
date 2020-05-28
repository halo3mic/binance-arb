import json

with open("../data/responses.json") as file:
	opp = json.load(file)

print(opp.keys())