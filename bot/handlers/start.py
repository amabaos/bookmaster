from datetime import datetime

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.models import ShopUser, Shop, AnalyticsEvent, UTMKey, BotLanguage
from bot.keyboards.captcha import build_captcha
from bot.keyboards.language import language_select_kb
from bot.keyboards.menu import main_menu_kb
from bot.utils import send_main_menu_msg, build_captcha_text


def create_router() -> Router:
    router = Router()

    @router.message(CommandStart())
    async def cmd_start(message: Message, db: AsyncSession, shop: Shop, shop_id: int):
        tg_id = message.from_user.id
        args = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""
        utm = args.strip() if args else ""

        result = await db.execute(
            select(ShopUser).where(ShopUser.shop_id == shop_id, ShopUser.tg_id == tg_id)
        )
        user = result.scalars().first()

        if user is None:
            user = ShopUser(
                shop_id=shop_id, tg_id=tg_id,
                username=message.from_user.username or "",
                first_name=message.from_user.first_name or "",
            )
            db.add(user)
            await db.flush()

        # Активация по UTM-ключу
        if utm and not user.is_activated:
            key_result = await db.execute(
                select(UTMKey).where(
                    UTMKey.shop_id == shop_id,
                    UTMKey.key == utm,
                    UTMKey.is_active == True,
                )
            )
            utm_key = key_result.scalars().first()
            if utm_key:
                user.is_activated = True
                user.utm_source = utm
                db.add(AnalyticsEvent(
                    shop_id=shop_id, tg_id=tg_id,
                    event_type="start", utm_source=utm,
                ))
                await db.flush()

        if not user.is_activated:
            return

        # Проверяем блок капчи
        if user.captcha_blocked_until:
            if user.captcha_blocked_until > datetime.utcnow():
                await message.answer("🚫 Доступ временно заблокирован. Попробуйте через час.")
                return
            else:
                # Блок истёк — сбрасываем, даём чистый старт
                user.captcha_blocked_until = None
                user.captcha_attempts = 0
                user.captcha_round = 0
                db.add(user)
                await db.flush()

        # Загружаем языки
        langs_result = await db.execute(
            select(BotLanguage)
            .where(BotLanguage.shop_id == shop_id, BotLanguage.is_active == True)
            .order_by(BotLanguage.sort_order, BotLanguage.id)
        )
        languages = langs_result.scalars().all()

        if languages and user.language_id is None:
            await message.answer(
                "🌐 Выберите язык / Select language:",
                reply_markup=language_select_kb(languages),
            )
            return

        language = None
        if user.language_id:
            language = await db.get(BotLanguage, user.language_id)

        if not user.captcha_passed:
            if utm:
                _, text, kb = build_captcha()
                current_round = user.captcha_round or 0
                await message.answer(build_captcha_text(current_round, text), reply_markup=kb)
            return

        await send_main_menu_msg(message, shop, reply_markup=main_menu_kb(), language=language)

    return router
