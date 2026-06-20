from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.models import Shop, ShopUser, Product, AnalyticsEvent, CryptoOption
from bot.keyboards.menu import payment_choice_kb, stars_pay_kb, crypto_coins_kb, crypto_back_kb
from bot.utils import edit_or_resend


def create_router() -> Router:
    router = Router()

    @router.callback_query(F.data.startswith("buy:"))
    async def buy_product(call: CallbackQuery, db: AsyncSession, shop: Shop, shop_user: ShopUser):
        product_id = int(call.data.split(":")[1])
        result = await db.execute(select(Product).where(Product.id == product_id))
        product = result.scalar_one_or_none()

        if not product or product.shop_id != shop.id:
            await call.answer("Товар не найден.", show_alert=True)
            return

        db.add(AnalyticsEvent(
            shop_id=shop.id, tg_id=call.from_user.id,
            event_type="click_pay", meta=str(product_id),
        ))

        has_stars = product.payment_type in ("stars", "both") and bool(product.stars_link)

        # Загружаем активные крипто-монеты из БД
        coins_result = await db.execute(
            select(CryptoOption)
            .where(CryptoOption.is_active == True)
            .order_by(CryptoOption.sort_order, CryptoOption.id)
        )
        coins = coins_result.scalars().all()
        has_crypto = product.payment_type in ("crypto", "both") and len(coins) > 0

        coins_list = [(c.symbol, c.id) for c in coins]

        if has_stars and not has_crypto:
            await _show_stars(call, product)
            return
        if has_crypto and not has_stars:
            await edit_or_resend(
                call.message, "🪙 Выберите монету:",
                reply_markup=crypto_coins_kb(product_id, coins_list),
            )
            await call.answer()
            return

        await edit_or_resend(
            call.message,
            "💳 Выберите способ оплаты:",
            reply_markup=payment_choice_kb(product_id, has_stars, has_crypto),
        )
        await call.answer()

    @router.callback_query(F.data.startswith("pay:stars:"))
    async def pay_stars(call: CallbackQuery, db: AsyncSession, shop: Shop):
        product_id = int(call.data.split(":")[2])
        result = await db.execute(select(Product).where(Product.id == product_id))
        product = result.scalar_one_or_none()
        if not product:
            await call.answer("Товар не найден.", show_alert=True)
            return
        await _show_stars(call, product)

    @router.callback_query(F.data.startswith("pay:crypto:"))
    async def pay_crypto_choose_coin(call: CallbackQuery, db: AsyncSession):
        product_id = int(call.data.split(":")[2])
        coins_result = await db.execute(
            select(CryptoOption)
            .where(CryptoOption.is_active == True)
            .order_by(CryptoOption.sort_order, CryptoOption.id)
        )
        coins = [(c.symbol, c.id) for c in coins_result.scalars().all()]
        await edit_or_resend(
            call.message, "🪙 Выберите монету:",
            reply_markup=crypto_coins_kb(product_id, coins),
        )
        await call.answer()

    @router.callback_query(F.data.startswith("pay:coin:"))
    async def pay_coin(call: CallbackQuery, db: AsyncSession, shop: Shop):
        parts = call.data.split(":")
        product_id = int(parts[2])
        coin_id = int(parts[3])

        coin = await db.get(CryptoOption, coin_id)
        if not coin:
            await call.answer("Монета не найдена.", show_alert=True)
            return

        result = await db.execute(select(Product).where(Product.id == product_id))
        product = result.scalar_one_or_none()
        price_str = f"${product.price_usd:.2f}" if product and product.price_usd else ""

        wallet = coin.wallet_address or "—"
        text = (
            f"🪙 <b>Оплата {coin.symbol}</b>"
            f"{' (' + coin.name + ')' if coin.name else ''}\n\n"
            f"{shop.crypto_message or 'Отправьте оплату на кошелёк и пришлите скриншот.'}\n\n"
            + (f"💰 Сумма: <b>{price_str}</b>\n" if price_str else "")
            + f"📋 Адрес кошелька:\n<code>{wallet}</code>\n\n"
            f"После оплаты отправьте скриншот в этот чат."
        )
        await edit_or_resend(call.message, text, reply_markup=crypto_back_kb())
        await call.answer()

    return router


async def _show_stars(call: CallbackQuery, product: Product):
    await edit_or_resend(
        call.message,
        "⭐ <b>Оплата Telegram Stars</b>\n\n"
        "Нажмите кнопку ниже, чтобы перейти к оплате.\n"
        "После оплаты вы получите доступ автоматически.",
        reply_markup=stars_pay_kb(product.stars_link),
    )
    await call.answer()
