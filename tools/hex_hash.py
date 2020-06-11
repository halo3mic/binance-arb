from math import log, ceil


def second_complement(num, nibs=18, base=16):
	nibs = ceil(log(abs(num), base)) + 1
	edge = int("F"*nibs, base)
	result = hex(num) if num > 0 else hex(edge + num + 1)
	result = result.lstrip("0x").upper()

	return result


print(second_complement(21772198568143187176))


