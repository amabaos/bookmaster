import random
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

EMOJIS = ["😀", "😂", "😍", "🤔", "😎", "🥳", "😴", "🤯", "👻", "🎃",
          "🐶", "🐱", "🦊", "🐸", "🐼", "🦁", "🐯", "🐨", "🦄", "🐙"]


def build_captcha() -> tuple[str, str, InlineKeyboardMarkup]:
    """Возвращает (правильный смайлик, текст вопроса, клавиатуру)"""
    choices = random.sample(EMOJIS, 4)
    correct = choices[0]
    random.shuffle(choices)

    buttons = [
        InlineKeyboardButton(text=e, callback_data=f"captcha:{'ok' if e == correct else 'fail'}")
        for e in choices
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=[buttons])
    text = f"Нажмите на смайлик: {correct}"
    return correct, text, kb
