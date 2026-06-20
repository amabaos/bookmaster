"""
Движок мультибота.
Режим работы определяется переменной WEBHOOK_HOST в .env:
  - Если задан  → webhook (Telegram шлёт обновления на твой домен)
  - Если не задан → polling (бот сам опрашивает Telegram, для локальной разработки)
"""
import os
import asyncio
import logging
from typing import Any, Awaitable, Callable

from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.models import Shop
from db.session import AsyncSessionLocal, init_db
from bot.crypto import decrypt_token
from bot.middlewares.db import DbMiddleware
from bot.middlewares.gate import GateMiddleware
from bot.handlers import start as start_mod, captcha as captcha_mod
from bot.handlers import menu as menu_mod, payment as payment_mod, wheel as wheel_mod
from bot.handlers import language as language_mod

logger = logging.getLogger(__name__)

WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "").rstrip("/")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

# shop_id -> (Bot, Dispatcher, asyncio.Task | None)
# Task = None в webhook-режиме
_active_bots: dict[int, tuple[Bot, Dispatcher, asyncio.Task | None]] = {}


class ShopMiddleware(BaseMiddleware):
    def __init__(self, shop: Shop):
        self.shop = shop
        super().__init__()

    async def __call__(self, handler: Callable[[Any, dict], Awaitable[Any]], event: Any, data: dict) -> Any:
        data["shop"] = self.shop
        data["shop_id"] = self.shop.id
        return await handler(event, data)


def _build_dispatcher(shop: Shop) -> Dispatcher:
    dp = Dispatcher()
    dp.update.middleware(DbMiddleware())
    dp.update.middleware(ShopMiddleware(shop))
    dp.update.middleware(GateMiddleware())
    dp.include_router(start_mod.create_router())
    dp.include_router(language_mod.create_router())
    dp.include_router(captcha_mod.create_router())
    dp.include_router(menu_mod.create_router())
    dp.include_router(payment_mod.create_router())
    dp.include_router(wheel_mod.create_router())
    return dp


def _make_bot(token: str) -> Bot:
    return Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


async def _update_username(bot: Bot, shop_id: int):
    try:
        me = await bot.get_me()
        async with AsyncSessionLocal() as db:
            shop_db = await db.get(Shop, shop_id)
            if shop_db:
                shop_db.username = me.username or ""
                await db.commit()
    except Exception:
        pass


# ── Polling ────────────────────────────────────────────────────────────────

async def _poll_bot(bot: Bot, dp: Dispatcher):
    try:
        await dp.start_polling(bot)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Polling error for bot {bot.id}: {e}")
    finally:
        await bot.session.close()


async def _start_shop_polling(shop: Shop):
    try:
        token = decrypt_token(shop.token_encrypted)
    except Exception as e:
        logger.error(f"Cannot decrypt token for shop {shop.id}: {e}")
        return

    bot = _make_bot(token)
    await _update_username(bot, shop.id)

    dp = _build_dispatcher(shop)
    task = asyncio.create_task(_poll_bot(bot, dp))
    _active_bots[shop.id] = (bot, dp, task)
    logger.info(f"[POLLING] Started bot for shop {shop.id} (@{shop.username})")


# ── Webhook ────────────────────────────────────────────────────────────────

async def _start_shop_webhook(shop: Shop):
    try:
        token = decrypt_token(shop.token_encrypted)
    except Exception as e:
        logger.error(f"Cannot decrypt token for shop {shop.id}: {e}")
        return

    bot = _make_bot(token)
    await _update_username(bot, shop.id)

    webhook_url = f"{WEBHOOK_HOST}/webhook/{shop.id}"
    await bot.set_webhook(
        url=webhook_url,
        secret_token=WEBHOOK_SECRET or None,
        drop_pending_updates=True,
    )
    dp = _build_dispatcher(shop)
    _active_bots[shop.id] = (bot, dp, None)
    logger.info(f"[WEBHOOK] Registered bot for shop {shop.id}: {webhook_url}")


# ── Public API ─────────────────────────────────────────────────────────────

async def start_shop(shop: Shop):
    if shop.id in _active_bots:
        logger.warning(f"Shop {shop.id} already running")
        return
    if WEBHOOK_HOST:
        await _start_shop_webhook(shop)
    else:
        await _start_shop_polling(shop)


async def stop_shop(shop_id: int):
    if shop_id not in _active_bots:
        return
    bot, dp, task = _active_bots.pop(shop_id)
    if task:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    else:
        try:
            await bot.delete_webhook()
        except Exception:
            pass
        await bot.session.close()
    logger.info(f"Stopped bot for shop {shop_id}")


async def start_all_shops():
    await init_db()
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Shop).where(Shop.is_active == True))
        shops = result.scalars().all()

    mode = "WEBHOOK" if WEBHOOK_HOST else "POLLING"
    logger.info(f"Starting {len(shops)} bots in {mode} mode...")
    await asyncio.gather(*[start_shop(shop) for shop in shops])


async def reload_shop(shop_id: int):
    await stop_shop(shop_id)
    async with AsyncSessionLocal() as db:
        shop = await db.get(Shop, shop_id)
        if shop and shop.is_active:
            await start_shop(shop)


def get_active_shop_ids() -> list[int]:
    return list(_active_bots.keys())


def get_bot_and_dp(shop_id: int) -> tuple[Bot, Dispatcher] | None:
    entry = _active_bots.get(shop_id)
    if entry:
        return entry[0], entry[1]
    return None
