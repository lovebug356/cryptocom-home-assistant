"""Tests for the sensor module."""
from unittest.mock import MagicMock

from custom_components.cryptocom.market_symbol import MarketSymbol

def test_parse_from_string():
    symbol = MarketSymbol.try_from_string('BTC/USD')
    assert symbol.base == 'BTC'
    assert symbol.quote == 'USD'

    symbol = MarketSymbol.try_from_string('ETH_USDT')
    assert symbol.base == 'ETH'
    assert symbol.quote == 'USDT'

def test_unit_of_measurement():
    assert MarketSymbol('BTC', 'USD').unit_of_measurement == '$'
    assert MarketSymbol('BTC', 'USDT').unit_of_measurement == 'USDT'
    assert MarketSymbol('BTC', 'EUR').unit_of_measurement == '€'

def test_name():
    assert MarketSymbol('BTC', 'USD').name == 'btc_usd'

def test_ccxt_symbol():
    assert MarketSymbol('BTC', 'USD').ccxt_symbol == 'BTC/USD'
