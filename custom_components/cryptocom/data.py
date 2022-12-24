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
        self.hass = hass
        self.exchange = ccxt.cryptocom({
            'rateLimit': 200,
            'asyncio_loop': hass.loop
        })
        self._markets = []
        self.tickers_coordinator = TickersCoordinator(self.hass, self.exchange)
        self._candlesticks_coordinator = {}

    async def async_setup(self) -> None:
        self._markets = await self.exchange.fetch_markets()

    def candlesticks_coordinator(self, market_symbol: MarketSymbol) -> CandlesticksCoordinator:
        result = self._candlesticks_coordinator.get(market_symbol.name, None)
        if not result:
            coordinator = CandlesticksCoordinator(self.hass, self.exchange, market_symbol)
            self._candlesticks_coordinator[market_symbol.name] = coordinator
            return coordinator
        else:
            return result

    def round_with_precision(self, value: float, symbol: MarketSymbol) -> int:
        precision: Optional[float] = None
        for market in self._markets:
            if market['symbol'] != symbol.ccxt_symbol:
                continue
            precision = market['precision']['price']
            break
        if not precision:
            _LOGGER.warning(f"failed to find market with symbol ${symbol.ccxt_symbol}")
            precision = 0.01
        return round_with_precision(value, precision)


class TickersCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, exchange: ccxt.cryptocom):
        super().__init__(hass, _LOGGER, name="cryptocom", update_interval=timedelta(minutes=5))
        self.exchange = exchange

    async def _async_update_data(self):
        return await self.exchange.fetch_tickers()

class CandlesticksCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, exchange: ccxt.cryptocom, symbol: MarketSymbol):
        super().__init__(hass, _LOGGER, name="cryptocom", update_interval=timedelta(minutes=10))
        self.exchange = exchange
        self.symbol = symbol

    async def _async_update_data(self):
        return await self.exchange.fetch_ohlcv(self.symbol.ccxt_symbol, '1h')