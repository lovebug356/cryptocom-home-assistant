"""The crypto.com integration."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Optional
import ccxt.async_support as ccxt
import async_timeout

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (DataUpdateCoordinator, CoordinatorEntity, UpdateFailed)

from .market_symbol import MarketSymbol
from .utils import round_with_precision

_LOGGER = logging.getLogger(__name__)

class CryptoComData:
    def __init__(self, hass: HomeAssistant) -> None:
        self.exchange = ccxt.cryptocom({
            'rateLimit': 200,
            'asyncio_loop': hass.loop
        })
        self.markets = []
        self.coordinator = CryptoComDataCoordinator(hass, self.exchange)

    async def async_setup(self) -> None:
        self.markets = await self.exchange.fetch_markets()
        _LOGGER.debug(f"found {len(self.markets)} markets on crypto.com exchange")


class CryptoComDataCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, exchange: ccxt.cryptocom):
        super().__init__(hass, _LOGGER, name="cryptocom", update_interval=timedelta(minutes=5))
        self.exchange = exchange
        self.markets = {}
        self.tickers = {}

    async def _async_update_data(self):
        _LOGGER.debug("fetch new data")
        async with async_timeout.timeout(20):
            await self._async_update_markets()
            self.tickers = await self.exchange.fetch_tickers()

    def fetch_last_price(self, symbol: MarketSymbol) -> Optional[str]:
        precision = self.fetch_price_precision(symbol)
        ticker = self.tickers.get(symbol.ccxt_symbol, None)
        if ticker:
            return round_with_precision(ticker['last'], precision)
        _LOGGER.warn(f"{symbol.ccxt_symbol} not found in the ticker list")
        return None

    async def _async_update_markets(self):
        if len(self.markets) == 0:
            self.markets = await self.exchange.fetch_markets()
            _LOGGER.debug(f"found {len(self.markets)} markets on crypto.com exchange")

    def fetch_price_precision(self, symbol: MarketSymbol) -> int:
        for market in self.markets:
            if market['symbol'] != symbol.ccxt_symbol:
                continue
            return market['precision']['price']
        _LOGGER.warning(f"failed to find market with symbol ${symbol.ccxt_symbol}")
        return 0.01