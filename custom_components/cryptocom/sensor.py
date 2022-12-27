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
from .const import CONF_TICKERS, CONF_TICKER_SYMBOL, DOMAIN, CONF_API_KEY, CONF_SECRET
from .market_symbol import MarketSymbol

SCAN_INTERVAL = timedelta(minutes=5)
_LOGGER = logging.getLogger(__name__)

TICKER_SCHEMA = vol.Schema(
    {vol.Required(CONF_TICKER_SYMBOL): cv.string}
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_API_KEY): cv.string,
        vol.Optional(CONF_SECRET): cv.string,
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

    cryptocom_data = CryptoComData(hass, config.get(CONF_API_KEY, None), config.get(CONF_SECRET, None))
    await cryptocom_data.async_setup()
    hass.data[DOMAIN] = cryptocom_data

    sensors = []
    if cryptocom_data.balance_coordinator:
        sensors.append(VirtualBalanceSensor(cryptocom_data, "Virtual Balance", "total"))
        sensors.append(VirtualBalanceSensor(cryptocom_data, "Free Balance", "free"))
    for ticker_config in config[CONF_TICKERS]:
        config_symbol = ticker_config[CONF_TICKER_SYMBOL]
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
        CurrencySensor.__init__(self, data, market_symbol)
        CoordinatorEntity.__init__(self, data.candlesticks_coordinator(market_symbol))
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
        
class VirtualBalanceSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, data: CryptoComData, name: str, property: str) -> None:
        SensorEntity.__init__(self) 
        CoordinatorEntity.__init__(self, data.balance_coordinator)
        self._data = data
        self._name = name
        self._property = property

    @property
    def unique_id(self) -> str:
        return self.name.lower().replace(' ', '_')

    @property
    def name(self) -> str:
        return f"Crypto.com {self._name}"

    @property
    def native_unit_of_measurement (self) -> str:
        return "$"

    @property
    def icon(self) -> str:
        return "mdi:currency-usd"

    @callback
    def _handle_coordinator_update(self) -> None:
        total = self.coordinator.data[self._property]
        virtual_total = total.get('USD', 0)
        tickers = self._data.tickers_coordinator.data
        if tickers:
            for currency in total.keys():
                if currency == 'USD':
                    continue
                currency_ticker = tickers.get(f'{currency}/USD', None)
                if currency_ticker:
                    virtual_total = virtual_total + currency_ticker['last'] * total[currency]
            self._attr_native_value = f"{virtual_total:.2f}"
            self.async_write_ha_state()
        else:
            _LOGGER.debug("no ticker data yet")