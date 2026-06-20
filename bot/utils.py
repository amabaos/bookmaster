"""Утилиты для работы с сообщениями."""
import os
from aiogram.types import Message, InlineKeyboardMarkup, FSInputFile, InputMediaPhoto
from aiogram.exceptions import TelegramBadRequest


def get_lang_text(language, shop, field: str, default: str = "") -> str:
    """Возвращает текст из языка, если задан, иначе из магазина."""
    if language:
        val = getattr(language, field, None)
        if val:
            return val
    return getattr(shop, field, None) or default


def get_menu_photo(language, shop) -> str:
    """Возвращает путь к фото меню: из языка → из магазина → пусто."""
    if language and getattr(language, "menu_photo", None):
        return language.menu_photo
    return getattr(shop, "menu_photo", None) or ""


async def edit_or_resend(
    message: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup = None,
    parse_mode: str = "HTML",
):
    """Редактирует текстовое сообщение или удаляет медиа и шлёт новое."""
    if message.text:
        try:
            await message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
            return
        except TelegramBadRequest:
            pass

    await message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
    try:
        await message.delete()
    except TelegramBadRequest:
        pass


def build_captcha_text(round_num: int, base_text: str, total: int = 3) -> str:
    """Прогресс-бар + текст капчи для указанного раунда."""
    progress = "🟢" * round_num + "⚪" * (total - round_num)
    return f"{progress}  Раунд {round_num + 1}/{total}\n\n{base_text}"


async def send_main_menu_msg(message: Message, shop, reply_markup, language=None):
    """Отправляет главное меню в ответ на Message (/start контекст)."""
    text = get_lang_text(language, shop, "menu_text", "Выберите раздел:")
    photo_path = get_menu_photo(language, shop)

    if photo_path and os.path.exists(photo_path):
        photo = FSInputFile(photo_path)
        await message.answer_photo(photo=photo, caption=text, reply_markup=reply_markup, parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=reply_markup, parse_mode="HTML")


async def resend_main_menu(message: Message, shop, reply_markup, language=None):
    """Обновляет сообщение до главного меню в callback-контексте."""
    text = get_lang_text(language, shop, "menu_text", "Выберите раздел:")
    photo_path = get_menu_photo(language, shop)

    if photo_path and os.path.exists(photo_path):
        photo = FSInputFile(photo_path)
        if message.photo:
            try:
                await message.edit_media(
                    InputMediaPhoto(media=photo, caption=text, parse_mode="HTML"),
                    reply_markup=reply_markup,
                )
                return
            except TelegramBadRequest:
                pass
        await message.answer_photo(photo=photo, caption=text, reply_markup=reply_markup, parse_mode="HTML")
        try:
            await message.delete()
        except TelegramBadRequest:
            pass
    else:
        await edit_or_resend(message, text, reply_markup=reply_markup)
