"""Platform for sensor integration."""
from __future__ import annotations

import logging
from typing import Optional
import voluptuous as vol
from datetime import timedelta

from homeassistant.components.sensor import SensorEntity, PLATFORM_SCHEMA
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.helpers.config_validation as cv

from .data import CandlesticksCoordinator, CryptoComData, TickersCoordinator
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
    if not hass.data[DOMAIN]:
        _LOGGER.error("I tought the component setup was done first!!!, I will stop setting up the sensor platform.")
        return

    cryptocom_data: CryptoComData = hass.data[DOMAIN]

    sensors = []
    if cryptocom_data.balance_coordinator:
        sensors.append(VirtualBalanceSensor(cryptocom_data, "Virtual Balance", "total"))
        sensors.append(VirtualBalanceSensor(cryptocom_data, "Free Balance", "free"))
    for ticker_config in config[CONF_TICKERS]:
        config_symbol = ticker_config[CONF_TICKER_SYMBOL]
        try:
            symbol = MarketSymbol.try_from_string(config_symbol)
            sensors.append(LastPriceSensor(cryptocom_data, cryptocom_data.tickers_coordinator, symbol))
            candlestick_coordinator = await cryptocom_data.candlesticks_coordinator(symbol)
            sensors.append(SimpleMovingAverage(cryptocom_data, candlestick_coordinator, symbol, 25))
            sensors.append(SimpleMovingAverage(cryptocom_data, candlestick_coordinator, symbol, 50))
            sensors.append(SimpleMovingAverage(cryptocom_data, candlestick_coordinator, symbol, 100))
            sensors.append(SimpleMovingAverage(cryptocom_data, candlestick_coordinator, symbol, 200))
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

    def __init__(self,
            data: CryptoComData,
            tickers_coordinator: TickersCoordinator,
            market_symbol: MarketSymbol) -> None:
        CoordinatorEntity.__init__(self, tickers_coordinator)
        CurrencySensor.__init__(self, data, market_symbol)

    @property
    def tickers_coordinator(self) -> TickersCoordinator:
        return self.coordinator

    @property
    def native_value(self) -> Optional[str]:
        last_price = self.tickers_coordinator.query_last_price(self._market_symbol)
        if not last_price:
            _LOGGER.warn("%s not found in the ticker list", self._market_symbol)
            return None
        return self.round_value(last_price)

class SimpleMovingAverage(CoordinatorEntity, CurrencySensor):
    def __init__(self,
            data: CryptoComData,
            candlestick_coordinator: CandlesticksCoordinator,
            market_symbol: MarketSymbol,
            period: int) -> None:
        CurrencySensor.__init__(self, data, market_symbol)
        CoordinatorEntity.__init__(self, candlestick_coordinator)
        self._period = period
        self.name_postfix = f"sma_{period}_1h"

    @property
    def native_value(self) -> Optional[str]:
        close_price_data = self.coordinator.data[-1 * self._period:]
        if len(close_price_data) == self._period:
            list = [a[3] for a in close_price_data]
            return self.round_value(sum(list) / len(list))
        else:
            _LOGGER.debug("not enough historic data for %s, need %d got %d", self._market_symbol, self._period, len(close_price_data))
            return None
        
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

    @property
    def native_value(self) -> Optional[str]:
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
            return f"{virtual_total:.2f}"
        else:
            _LOGGER.debug("no ticker data yet")
            return None