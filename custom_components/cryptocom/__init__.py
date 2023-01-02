"""The Crypto.com integration."""
from __future__ import annotations

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import CONF_API_KEY, CONF_SECRET, DOMAIN
from .data import CryptoComData
from .market_buy_and_limit_sell import CreateMarketBuyAndLimitSellService

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    cryptocom_config = config[DOMAIN]
    cryptocom_data = CryptoComData(hass, cryptocom_config.get(CONF_API_KEY, None), cryptocom_config.get(CONF_SECRET, None))
    await cryptocom_data.async_setup()
    hass.data[DOMAIN] = cryptocom_data

    hass.services.async_register(DOMAIN, "market_buy_and_limit_sell", CreateMarketBuyAndLimitSellService(cryptocom_data))

    return True