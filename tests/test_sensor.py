"""Tests for the sensor module."""
from unittest.mock import MagicMock

from custom_components.cryptocom.market_symbol import MarketSymbol
from custom_components.cryptocom.sensor import LastPriceSensor

async def test_basic_properties():
    cryptocom_data = MagicMock()
    coordinator = MagicMock()

    sensor = LastPriceSensor(cryptocom_data, coordinator, MarketSymbol.try_from_string("BTC/USD"))
    assert sensor.unit_of_measurement == '$'
    assert sensor.name == 'btc_usd_last_price'

    sensor = LastPriceSensor(cryptocom_data, coordinator, MarketSymbol.try_from_string("BTC/EUR"))
    assert sensor.unit_of_measurement == '€'

    sensor = LastPriceSensor(cryptocom_data, coordinator, MarketSymbol.try_from_string("BTC/USDT"))
    assert sensor.unit_of_measurement == 'USDT'