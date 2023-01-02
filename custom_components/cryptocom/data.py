"""The crypto.com integration."""
from __future__ import annotations

import logging
import asyncio
from datetime import timedelta
from typing import Optional
import ccxt.async_support as ccxt

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (DataUpdateCoordinator, CoordinatorEntity, UpdateFailed)

from .market_symbol import MarketSymbol
from .utils import round_with_precision

_LOGGER = logging.getLogger(__name__)

class CryptoComData:
    def __init__(self, hass: HomeAssistant, api_key: Optional[str] = None, secret: Optional[str] = None) -> None:
        self.hass = hass
        self.exchange = ccxt.cryptocom({
            'apiKey': api_key,
            'secret': secret,
            'rateLimit': 200,
            'asyncio_loop': hass.loop
        })
        self._markets = []
        self.tickers_coordinator = TickersCoordinator(self.hass, self.exchange)
        self.balance_coordinator: Optional[BalanceCoordinator] = None
        if api_key is not None and secret is not None:
            self.balance_coordinator = BalanceCoordinator(self.hass, self.exchange)
        self._candlesticks_coordinator = {}

    async def async_setup(self) -> None:
        self._markets = await self.exchange.fetch_markets()
        await self.tickers_coordinator.async_config_entry_first_refresh()
        if self.balance_coordinator:
            await self.balance_coordinator.async_config_entry_first_refresh()

    async def wait_until_order_closed(self, order):
        while order ['status'] != 'closed':
            await asyncio.sleep(0.3)
            order = await self.exchange.fetch_order(order['id'])
        return order

    async def fetch_free_balance(self, currency: str) -> float:
        if not self.balance_coordinator:
            _LOGGER.error("I can't query free balance if you don't give me credentials")
            raise Exception("failed to get free balance, no balance coordinator available")
        await self.balance_coordinator.async_request_refresh()
        self.balance_coordinator.data['']
        return 0

    async def candlesticks_coordinator(self, market_symbol: MarketSymbol) -> CandlesticksCoordinator:
        result = self._candlesticks_coordinator.get(market_symbol.name, None)
        if not result:
            coordinator = CandlesticksCoordinator(self.hass, self.exchange, market_symbol)
            await coordinator.async_config_entry_first_refresh()
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

class BalanceCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, exchange: ccxt.cryptocom):
        super().__init__(hass, _LOGGER, name="cryptocom", update_interval=timedelta(minutes=11))
        self.exchange = exchange

    async def fetch_free_balance(self, currency: str) -> float:
        await self.async_refresh()
        return self.data['free'][currency]

    async def _async_update_data(self):
        return await self.exchange.fetch_balance()

class TickersCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, exchange: ccxt.cryptocom):
        super().__init__(hass, _LOGGER, name="cryptocom", update_interval=timedelta(minutes=5))
        self.exchange = exchange

    def query_last_price(self, symbol: MarketSymbol) -> Optional[str]:
        ticker = self.data.get(symbol.ccxt_symbol, None)
        if not ticker:
            return None
        return ticker['last']

    async def _async_update_data(self):
        return await self.exchange.fetch_tickers()

class CandlesticksCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, exchange: ccxt.cryptocom, symbol: MarketSymbol):
        super().__init__(hass, _LOGGER, name="cryptocom", update_interval=timedelta(minutes=10))
        self.exchange = exchange
        self.symbol = symbol

    async def _async_update_data(self):
        return await self.exchange.fetch_ohlcv(self.symbol.ccxt_symbol, '1h')