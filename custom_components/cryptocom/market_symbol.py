from __future__ import annotations
from dataclasses import dataclass

@dataclass
class MarketSymbol:
    base: str
    quote: str

    def __str__(self) -> str:
        return self.ccxt_symbol

    @staticmethod
    def try_from_string(data: str) -> MarketSymbol:
        split_data = data.replace('_', '/').split('/')
        return MarketSymbol(split_data[0], split_data[1])

    @property
    def name(self) -> str:
        return f"{self.base}_{self.quote}".lower()

    @property
    def ccxt_symbol(self) -> str:
        return f"{self.base}/{self.quote}"

    @property
    def unit_of_measurement(self) -> str:
        if self.quote == 'USD':
            return '$'
        elif self.quote == 'EUR':
            return '€'
        else:
            return self.quote