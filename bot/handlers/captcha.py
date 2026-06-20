from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ShopUser, Shop, BotLanguage
from bot.keyboards.menu import main_menu_kb
from bot.keyboards.captcha import build_captcha
from bot.utils import edit_or_resend, resend_main_menu

TOTAL_ROUNDS = 3
MAX_ATTEMPTS = 2
BLOCK_HOURS = 1


def _captcha_msg(round_num: int, base_text: str) -> str:
    """Формирует текст капчи с прогрессом."""
    progress = "🟢" * round_num + "⚪" * (TOTAL_ROUNDS - round_num)
    return f"{progress}  Раунд {round_num + 1}/{TOTAL_ROUNDS}\n\n{base_text}"


def create_router() -> Router:
    router = Router()

    @router.callback_query(F.data.startswith("captcha:"))
    async def captcha_answer(
        call: CallbackQuery,
        db: AsyncSession,
        shop: Shop,
        shop_user: ShopUser,
        language: BotLanguage = None,
    ):
        # Проверяем блок (на случай если callback пришёл из старого сообщения)
        if shop_user.captcha_blocked_until and shop_user.captcha_blocked_until > datetime.utcnow():
            await call.answer("🚫 Вы заблокированы. Попробуйте через час.", show_alert=True)
            return

        result = call.data.split(":")[1]

        if result == "ok":
            shop_user.captcha_round = (shop_user.captcha_round or 0) + 1

            if shop_user.captcha_round >= TOTAL_ROUNDS:
                # Все раунды пройдены
                shop_user.captcha_passed = True
                shop_user.captcha_round = 0
                shop_user.captcha_attempts = 0
                db.add(shop_user)
                await db.flush()
                await resend_main_menu(call.message, shop, reply_markup=main_menu_kb(), language=language)
            else:
                # Следующий раунд
                db.add(shop_user)
                _, text, kb = build_captcha()
                await edit_or_resend(
                    call.message,
                    f"✅ Верно!\n\n{_captcha_msg(shop_user.captcha_round, text)}",
                    reply_markup=kb,
                )
        else:
            # Неверный ответ — сброс раунда, +1 к попыткам
            shop_user.captcha_round = 0
            shop_user.captcha_attempts = (shop_user.captcha_attempts or 0) + 1

            if shop_user.captcha_attempts >= MAX_ATTEMPTS:
                # Блок на час
                shop_user.captcha_blocked_until = datetime.utcnow() + timedelta(hours=BLOCK_HOURS)
                db.add(shop_user)
                await edit_or_resend(
                    call.message,
                    "🚫 <b>Слишком много неудачных попыток.</b>\n\n"
                    "Доступ заблокирован на 1 час. Попробуйте позже.",
                )
            else:
                remaining = MAX_ATTEMPTS - shop_user.captcha_attempts
                db.add(shop_user)
                _, text, kb = build_captcha()
                await edit_or_resend(
                    call.message,
                    f"❌ Неверно! Капча сброшена.\n"
                    f"Осталось попыток: <b>{remaining}</b>\n\n"
                    f"{_captcha_msg(0, text)}",
                    reply_markup=kb,
                )

        await call.answer()

    return router
