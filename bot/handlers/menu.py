from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.models import Shop, Product, BotLanguage, ProductTranslation
from bot.keyboards.menu import main_menu_kb, products_back_kb, product_kb
from bot.utils import edit_or_resend, resend_main_menu, get_lang_text


def create_router() -> Router:
    router = Router()

    @router.callback_query(F.data == "menu:main")
    async def to_main_menu(call: CallbackQuery, shop: Shop, language: BotLanguage = None):
        await resend_main_menu(call.message, shop, reply_markup=main_menu_kb(), language=language)
        await call.answer()

    @router.callback_query(F.data == "menu:support")
    async def support(call: CallbackQuery, shop: Shop, language: BotLanguage = None):
        text = get_lang_text(language, shop, "support_text", "Напишите нам.")
        await edit_or_resend(call.message, text, reply_markup=products_back_kb())
        await call.answer()

    @router.callback_query(F.data == "menu:shop")
    async def product_list(call: CallbackQuery, db: AsyncSession, shop: Shop, language: BotLanguage = None):
        result = await db.execute(
            select(Product)
            .where(Product.shop_id == shop.id, Product.is_active == True)
            .order_by(Product.sort_order, Product.id)
        )
        products = result.scalars().all()

        if not products:
            await edit_or_resend(
                call.message, "Товары пока не добавлены.",
                reply_markup=products_back_kb(),
            )
            await call.answer()
            return

        # Загружаем переводы одним запросом
        tr_map: dict[int, ProductTranslation] = {}
        if language:
            product_ids = [p.id for p in products]
            tr_result = await db.execute(
                select(ProductTranslation).where(
                    ProductTranslation.product_id.in_(product_ids),
                    ProductTranslation.language_id == language.id,
                )
            )
            for tr in tr_result.scalars().all():
                tr_map[tr.product_id] = tr

        rows = []
        for p in products:
            tr = tr_map.get(p.id)
            name = (tr.name if tr and tr.name else None) or p.name
            rows.append([InlineKeyboardButton(text=name, callback_data=f"product:{p.id}")])
        rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main")])

        await edit_or_resend(
            call.message, "🛍 <b>Каталог товаров</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        )
        await call.answer()

    @router.callback_query(F.data.startswith("product:"))
    async def product_card(call: CallbackQuery, db: AsyncSession, shop: Shop, language: BotLanguage = None):
        product_id = int(call.data.split(":")[1])
        result = await db.execute(select(Product).where(Product.id == product_id))
        product = result.scalar_one_or_none()

        if not product or product.shop_id != shop.id:
            await call.answer("Товар не найден.", show_alert=True)
            return

        # Ищем перевод
        tr = None
        if language:
            tr_result = await db.execute(
                select(ProductTranslation).where(
                    ProductTranslation.product_id == product_id,
                    ProductTranslation.language_id == language.id,
                )
            )
            tr = tr_result.scalar_one_or_none()

        description = (tr.description if tr and tr.description else None) or product.description or f"<b>{product.name}</b>"
        image_path = (tr.image_path if tr and tr.image_path else None) or product.image_path or ""

        import os
        if image_path and os.path.exists(image_path):
            from aiogram.types import FSInputFile
            from aiogram.exceptions import TelegramBadRequest
            photo = FSInputFile(image_path)
            if call.message.photo:
                try:
                    from aiogram.types import InputMediaPhoto
                    await call.message.edit_media(
                        InputMediaPhoto(media=photo, caption=description, parse_mode="HTML"),
                        reply_markup=product_kb(product_id),
                    )
                    await call.answer()
                    return
                except TelegramBadRequest:
                    pass
            await call.message.answer_photo(
                photo=photo, caption=description,
                reply_markup=product_kb(product_id), parse_mode="HTML",
            )
            try:
                await call.message.delete()
            except TelegramBadRequest:
                pass
            await call.answer()
            return

        await edit_or_resend(call.message, description, reply_markup=product_kb(product_id))
        await call.answer()

    return router
