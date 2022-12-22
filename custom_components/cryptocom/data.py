"""The crypto.com integration."""
from __future__ import annotations

import logging
import ccxt.async_support as ccxt

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

class CryptoComData:
    def __init__(self, hass: HomeAssistant) -> None:
        self.exchange = ccxt.cryptocom({
            'rateLimit': 200,
            'asyncio_loop': hass.loop
        })
        self.markets = []

    async def async_setup(self) -> None:
        self.markets = await self.exchange.fetch_markets()
        _LOGGER.debug(f"found {len(self.markets)} markets on crypto.com exchange")

    def fetch_price_precision(self, symbol) -> int:
        for market in self.markets:
            if market['symbol'] != symbol:
                continue
            return market['precision']['price']
        _LOGGER.warning(f"failed to find market with symbol ${symbol}")
        return 0.01