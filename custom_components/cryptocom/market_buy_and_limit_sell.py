"""The Crypto.com integration."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from homeassistant.const import Platform

from .const import SERVICE_FIELD_SELL_PROFIT, SERVICE_FIELD_SYMBOL, SERVICE_FIELD_BUY_PERCENTAGE
from .data import CryptoComData

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

@dataclass
class MarketBuyAndLimitSellData:
    symbol: str
    buy_percentage: float
    sell_profit: float

    @staticmethod
    def try_from_data(data: any) -> MarketBuyAndLimitSellData:
        return MarketBuyAndLimitSellData(
            data.get(SERVICE_FIELD_SYMBOL),
            data.get(SERVICE_FIELD_BUY_PERCENTAGE) / 100,
            data.get(SERVICE_FIELD_SELL_PROFIT) / 100,
        )

    def create_client_oid(self) -> str:
        return f"ha-mbals-B{self.buy_percentage * 100}-P{self.sell_profit * 100}-{time.time()}".replace(",", "").replace(".", "")

def CreateMarketBuyAndLimitSellService(cryptocom_data: CryptoComData):

    async def market_buy_and_limit_sell(call):
        service_data = MarketBuyAndLimitSellData.try_from_data(call.data)

        free_usd = (await cryptocom_data.exchange.fetch_balance())['free']['USD']
        available_for_order = free_usd * service_data.buy_percentage
        btc_price = (await cryptocom_data.exchange.fetch_ticker(service_data.symbol))['last']
        buy_amount = available_for_order / btc_price

        _LOGGER.debug("I'm creating a market buy order on %s for %f coins", service_data.symbol, buy_amount)
        buy_order = await cryptocom_data.exchange.create_market_buy_order(service_data.symbol, buy_amount)

        buy_order = await cryptocom_data.wait_until_order_closed(buy_order)

        sell_amount = buy_order['amount']
        sell_price = buy_order['price'] * (1 + service_data.sell_profit)
        _LOGGER.debug("I'm creating a limit sell order on %s for %f coins with price %f", service_data.symbol, sell_amount, sell_price)
        await cryptocom_data.exchange.create_limit_sell_order(service_data.symbol, sell_amount, sell_price, { 'client_oid': service_data.create_client_oid()})
        await cryptocom_data.balance_coordinator.async_request_refresh()

    return market_buy_and_limit_sell