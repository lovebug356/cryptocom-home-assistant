"""Platform for sensor integration."""
from __future__ import annotations

import logging
import voluptuous as vol
from datetime import timedelta

from homeassistant.components.sensor import SensorEntity, PLATFORM_SCHEMA
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.helpers.config_validation as cv

from .data import CryptoComData
from .const import CONF_TICKERS, CONF_TICKER_SYMBOL, DOMAIN
from .market_symbol import MarketSymbol

SCAN_INTERVAL = timedelta(minutes=5)
_LOGGER = logging.getLogger(__name__)

TICKER_SCHEMA = vol.Schema(
    {vol.Required(CONF_TICKER_SYMBOL): cv.string}
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_TICKERS): vol.All(cv.ensure_list, [TICKER_SCHEMA]),
    }
)

async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""

    cryptocom_data = CryptoComData(hass)
    await cryptocom_data.async_setup()
    hass.data[DOMAIN] = cryptocom_data

    sensors = []
    for data in config[CONF_TICKERS]:
        config_symbol = data[CONF_TICKER_SYMBOL]
        try:
            symbol = MarketSymbol.try_from_string(config_symbol)
            sensors.append(LastPriceSensor(cryptocom_data, symbol))
            sensors.append(SimpleMovingAverage(cryptocom_data, symbol, 25))
            sensors.append(SimpleMovingAverage(cryptocom_data, symbol, 50))
            sensors.append(SimpleMovingAverage(cryptocom_data, symbol, 100))
            sensors.append(SimpleMovingAverage(cryptocom_data, symbol, 200))
        except Exception as err:
            _LOGGER.warn(f"failed to parse '{config_symbol}' as valid market symbol: ${err}")

    add_entities(sensors, update_before_add=True)

class CurrencySensor(SensorEntity):
    name_postfix: str

    def __init__(self, data: CryptoComData, symbol: MarketSymbol) -> None:
        self._data = data
        self._market_symbol = symbol

    @property
    def unique_id(self) -> str:
        return f"{self._market_symbol.name}_{self.name_postfix}"

    @property
    def name(self) -> str:
        return f"{self._market_symbol.name}_{self.name_postfix}"

    @property
    def native_unit_of_measurement (self) -> str:
        """Return the unit of measurement."""
        return self._market_symbol.unit_of_measurement

    @property
    def icon(self) -> str:
        """Return the icon."""
        if self._market_symbol.base == "EUR":
            return "mdi:currency-eur"
        elif self._market_symbol.base == "USD":
            return "mdi:currency-usd"
        elif self._market_symbol.base == "BTC":
            return "mdi:currency-btc"
        else:
            return "mdi:cash"

    def round_value(self, value: float) -> str:
        return self._data.round_with_precision(value, self._market_symbol)

class LastPriceSensor(CoordinatorEntity, CurrencySensor):
    name_postfix: str = 'last_price'

    def __init__(self, data: CryptoComData, market_symbol: MarketSymbol) -> None:
        CoordinatorEntity.__init__(self, data.tickers_coordinator)
        CurrencySensor.__init__(self, data, market_symbol)
        self._data = data

    @property
    def state(self) -> str:
        return self._attr_native_value

    @callback
    def _handle_coordinator_update(self) -> None:
        ticker = self._data.tickers_coordinator.data.get(self._market_symbol.ccxt_symbol, None)
        if ticker:
            self._attr_native_value = self.round_value(ticker['last'])
            self.async_write_ha_state()
            return
        _LOGGER.warn(f"{self._market_symbol.ccxt_symbol} not found in the ticker list")

class SimpleMovingAverage(CoordinatorEntity, CurrencySensor):
    def __init__(self, data: CryptoComData, market_symbol: MarketSymbol, period: int) -> None:
        CoordinatorEntity.__init__(self, data.candlesticks_coordinator(market_symbol))
        CurrencySensor.__init__(self, data, market_symbol)
        self._data = data
        self._period = period
        self.name_postfix = f"sma_{period}_1h"

    @property
    def state(self) -> str:
        return self._attr_native_value

    @callback
    def _handle_coordinator_update(self) -> None:
        close_price_data = self.coordinator.data[-1 * self._period:]
        if len(close_price_data) == self._period:
            list = [a[3] for a in close_price_data]
            self._attr_native_value = self.round_value(sum(list) / len(list))
            self.async_write_ha_state()
            return
        else:
            _LOGGER.debug("not enough historic data for %s, need %d got %d", self._market_symbol.ccxt_symbol, self._period, len(close_price_data))
            self._attr_native_value = None
            self.async_write_ha_state()
            return