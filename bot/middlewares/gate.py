from datetime import datetime
from typing import Any, Awaitable, Callable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, Update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.models import ShopUser, BotLanguage


class GateMiddleware(BaseMiddleware):
    """
    Пропускает только пользователей, активированных по UTM-метке.
    Активация происходит в handlers/start.py при /start?start=<метка>.
    Дополнительно: прокидывает data["language"] с выбранным языком пользователя.
    """

    async def __call__(
        self,
        handler: Callable[[Any, dict], Awaitable[Any]],
        event: Any,
        data: dict,
    ) -> Any:
        if isinstance(event, Update):
            inner = event.message or event.callback_query
        else:
            inner = event

        if inner is None:
            return await handler(event, data)

        tg_id = inner.from_user.id
        shop_id: int = data.get("shop_id")
        db: AsyncSession = data.get("db")

        if not shop_id or not db:
            return await handler(event, data)

        # /start всегда пропускаем — активация происходит внутри хендлера
        if isinstance(inner, Message) and inner.text and inner.text.startswith("/start"):
            return await handler(event, data)

        result = await db.execute(
            select(ShopUser).where(
                ShopUser.shop_id == shop_id,
                ShopUser.tg_id == tg_id,
                ShopUser.is_activated == True,
            )
        )
        user = result.scalars().first()

        if user is None:
            return

        data["shop_user"] = user

        # Проверяем блок капчи
        if user.captcha_blocked_until:
            if user.captcha_blocked_until > datetime.utcnow():
                # Ещё заблокирован
                if isinstance(inner, CallbackQuery) and not inner.data.startswith("lang_select:"):
                    await inner.answer("🚫 Доступ заблокирован. Попробуйте через час.", show_alert=True)
                    return
                elif isinstance(inner, Message):
                    return
            else:
                # Блок истёк — сбрасываем счётчики, даём чистый старт
                user.captcha_blocked_until = None
                user.captcha_attempts = 0
                user.captcha_round = 0
                db.add(user)
                await db.flush()

        # Загружаем язык пользователя
        language = None
        if user.language_id:
            language = await db.get(BotLanguage, user.language_id)
        data["language"] = language

        return await handler(event, data)
