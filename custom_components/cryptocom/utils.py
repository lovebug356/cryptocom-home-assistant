import math

def round_with_precision(value: float, precision: float) -> str:
    price_precision = round(math.log10(1/precision))
    return "{0:.{1}f}".format(value, price_precision)