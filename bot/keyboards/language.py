from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def language_select_kb(languages) -> InlineKeyboardMarkup:
    rows = []
    for lang in languages:
        label = f"{lang.flag_emoji} {lang.name}".strip() if lang.flag_emoji else lang.name
        rows.append([InlineKeyboardButton(
            text=label,
            callback_data=f"lang_select:{lang.id}",
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows)
