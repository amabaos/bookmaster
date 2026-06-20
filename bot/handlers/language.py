from datetime import datetime

from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Shop, ShopUser, BotLanguage
from bot.keyboards.captcha import build_captcha
from bot.keyboards.menu import main_menu_kb
from bot.utils import edit_or_resend, resend_main_menu, build_captcha_text


def create_router() -> Router:
    router = Router()

    @router.callback_query(F.data.startswith("lang_select:"))
    async def select_language(call: CallbackQuery, db: AsyncSession, shop: Shop, shop_user: ShopUser):
        lang_id = int(call.data.split(":")[1])
        lang = await db.get(BotLanguage, lang_id)

        if not lang or lang.shop_id != shop.id or not lang.is_active:
            await call.answer("Язык недоступен.", show_alert=True)
            return

        shop_user.language_id = lang_id
        db.add(shop_user)
        await db.flush()
        await call.answer()

        if not shop_user.captcha_passed:
            # Проверяем блок
            if shop_user.captcha_blocked_until and shop_user.captcha_blocked_until > datetime.utcnow():
                await edit_or_resend(call.message, "🚫 Доступ временно заблокирован. Попробуйте через час.")
                return
            _, text, kb = build_captcha()
            current_round = shop_user.captcha_round or 0
            await edit_or_resend(call.message, build_captcha_text(current_round, text), reply_markup=kb)
        else:
            await resend_main_menu(call.message, shop, reply_markup=main_menu_kb(), language=lang)

    return router
