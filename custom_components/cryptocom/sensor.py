"""Platform for sensor integration."""
from __future__ import annotations

import logging
import voluptuous as vol
from datetime import timedelta
from typing import Dict, Optional
from ccxt.base.errors import BadSymbol

from homeassistant.components.sensor import SensorEntity, PLATFORM_SCHEMA
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.helpers.config_validation as cv

from .data import CryptoComData, CryptoComDataCoordinator
from .const import CONF_TICKERS, CONF_TICKER_SYMBOL, DOMAIN
from .utils import round_with_precision
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
            sensors.append(LastPriceSensor(cryptocom_data.coordinator, symbol))
        except:
            _LOGGER.warn(f"failed to parse '{config_symbol}' as valid market symbol")

    add_entities(sensors, update_before_add=True)

class LastPriceSensor(CoordinatorEntity, SensorEntity):
    """Representation of a ticker sensor."""

    def __init__(self, coordinator: CryptoComDataCoordinator, market_symbol: MarketSymbol) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._market_symbol = market_symbol
        self._name = f"{self._market_symbol.name}_last_price"
        self._state = None

    @property
    def unique_id(self) -> str:
        """Return the unique id of the sensor."""
        return self._name

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self) -> Optional[str]:
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self) -> str:
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

    @callback
    def _handle_coordinator_update(self) -> None:
        self._state = self.coordinator.fetch_last_price(self._market_symbol)
        self.async_write_ha_state()