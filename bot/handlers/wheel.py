import random
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.models import Shop, ShopUser, WheelFile, AnalyticsEvent

SPIN_INTERVAL_HOURS = 24

_back_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main")]
])
_spin_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🎡 Крутить!", callback_data="wheel:spin")],
    [InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main")],
])


def create_router() -> Router:
    router = Router()

    @router.callback_query(F.data == "menu:wheel")
    async def wheel_menu(call: CallbackQuery, shop: Shop, shop_user: ShopUser):
        now = datetime.utcnow()
        if shop_user.wheel_last_spin:
            next_spin = shop_user.wheel_last_spin + timedelta(hours=SPIN_INTERVAL_HOURS)
            if now < next_spin:
                remaining = next_spin - now
                hours = int(remaining.total_seconds() // 3600)
                minutes = int((remaining.total_seconds() % 3600) // 60)
                await call.message.edit_text(
                    f"🎡 <b>Колесо фортуны</b>\n\n"
                    f"⏳ Следующая прокрутка через: <b>{hours}ч {minutes}мин</b>",
                    reply_markup=_back_kb, parse_mode="HTML",
                )
                await call.answer()
                return

        await call.message.edit_text(
            "🎡 <b>Колесо фортуны</b>\n\nКруть и получи приз!",
            reply_markup=_spin_kb, parse_mode="HTML",
        )
        await call.answer()

    @router.callback_query(F.data == "wheel:spin")
    async def wheel_spin(call: CallbackQuery, db: AsyncSession, shop: Shop, shop_user: ShopUser):
        now = datetime.utcnow()

        if shop_user.wheel_last_spin:
            next_spin = shop_user.wheel_last_spin + timedelta(hours=SPIN_INTERVAL_HOURS)
            if now < next_spin:
                await call.answer("Подожди до следующей прокрутки!", show_alert=True)
                return

        result = await db.execute(
            select(WheelFile).where(WheelFile.shop_id == shop.id).order_by(WheelFile.sort_order)
        )
        files = result.scalars().all()

        if not files:
            await call.answer("Файлы для колеса ещё не загружены.", show_alert=True)
            return

        candidates = [f for f in files if f.id != shop_user.wheel_last_file_id]
        if not candidates:
            candidates = files

        chosen = random.choice(candidates)
        shop_user.wheel_last_spin = now
        shop_user.wheel_last_file_id = chosen.id
        db.add(shop_user)
        db.add(AnalyticsEvent(shop_id=shop.id, tg_id=call.from_user.id, event_type="wheel_spin"))

        import os
        menu_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ В меню", callback_data="menu:main")]
        ])

        if not os.path.exists(chosen.file_path):
            await call.message.edit_text("Файл не найден.", reply_markup=menu_kb)
            await call.answer()
            return

        file = FSInputFile(chosen.file_path)
        caption = "🎉 Твой приз!"

        if chosen.file_type == "photo":
            await call.message.answer_photo(photo=file, caption=caption, reply_markup=menu_kb)
        elif chosen.file_type == "video":
            await call.message.answer_video(video=file, caption=caption, reply_markup=menu_kb)
        else:
            await call.message.answer_document(document=file, caption=caption, reply_markup=menu_kb)

        await call.message.delete()
        await call.answer("🎡 Удача!")

    return router
