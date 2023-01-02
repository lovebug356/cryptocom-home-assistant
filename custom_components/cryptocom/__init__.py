"""The Crypto.com integration."""
from __future__ import annotations

import logging
import asyncio

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import CONF_API_KEY, CONF_SECRET, DOMAIN
from .data import CryptoComData

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    cryptocom_config = config[DOMAIN]
    cryptocom_data = CryptoComData(hass, cryptocom_config.get(CONF_API_KEY, None), cryptocom_config.get(CONF_SECRET, None))
    await cryptocom_data.async_setup()
    hass.data[DOMAIN] = cryptocom_data

    async def market_buy_and_limit_sell(call):
        symbol = call.data.get("symbol", None)
        buy_percentage = call.data.get("buy_percentage", 1) / 100
        sell_percentage = call.data.get("sell_profit", 1) / 100

        free_usd = (await cryptocom_data.exchange.fetch_balance())['free']['USD']
        available_for_order = free_usd * buy_percentage
        btc_price = (await cryptocom_data.exchange.fetch_ticker('BTC/USD'))['last']
        buy_amount = available_for_order / btc_price

        _LOGGER.debug("I'm creating a market buy order on %s for %f coins", symbol, buy_amount)
        buy_order = await cryptocom_data.exchange.create_market_buy_order(symbol, buy_amount)

        while buy_order['status'] != 'closed':
            await asyncio.sleep(0.3)
            buy_order = await cryptocom_data.exchange.fetch_order(buy_order['id'])
        _LOGGER.debug("I bought %f for the price %f", buy_order['amount'], buy_order['price'])

        sell_amount = buy_order['amount']
        sell_price = buy_order['price'] * (1 + sell_percentage)
        _LOGGER.debug("I'm creating a limit sell order on %s for %f coins with price %f", symbol, sell_amount, sell_price)
        await cryptocom_data.exchange.create_limit_sell_order('BTC/USD', sell_amount, sell_price)

    hass.services.async_register(DOMAIN, "market_buy_and_limit_sell", market_buy_and_limit_sell)

    return True