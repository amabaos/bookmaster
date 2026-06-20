from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍 Товары", callback_data="menu:shop")],
        [InlineKeyboardButton(text="🎡 Колесо фортуны", callback_data="menu:wheel")],
        [InlineKeyboardButton(text="💬 Поддержка", callback_data="menu:support")],
    ])


def products_back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main")]
    ])


def product_kb(product_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Купить", callback_data=f"buy:{product_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="menu:shop")],
    ])


def payment_choice_kb(product_id: int, has_stars: bool, has_crypto: bool) -> InlineKeyboardMarkup:
    rows = []
    if has_stars:
        rows.append([InlineKeyboardButton(text="⭐ Telegram Stars", callback_data=f"pay:stars:{product_id}")])
    if has_crypto:
        rows.append([InlineKeyboardButton(text="🪙 Крипта", callback_data=f"pay:crypto:{product_id}")])
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data=f"product:{product_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def stars_pay_kb(link: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Оплатить Stars", url=link)],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="menu:shop")],
    ])


def crypto_coins_kb(product_id: int, coins: list) -> InlineKeyboardMarkup:
    """coins — список (symbol, coin_id) из БД"""
    rows = [[InlineKeyboardButton(
        text=symbol,
        callback_data=f"pay:coin:{product_id}:{coin_id}"
    )] for symbol, coin_id in coins]
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data=f"buy:{product_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def crypto_back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="menu:main")]
    ])
