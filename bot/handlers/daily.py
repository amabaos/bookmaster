"""Ежедневное сообщение — отправляется при входе в меню раз в 24 часа"""
from datetime import datetime, timedelta
from aiogram.types import Message, FSInputFile
import os


async def maybe_send_daily(message: Message, shop, shop_user, db):
    if not shop.daily_message_text and not shop.daily_message_media:
        return

    now = datetime.utcnow()
    if shop_user.daily_msg_last_sent:
        if now - shop_user.daily_msg_last_sent < timedelta(hours=24):
            return

    shop_user.daily_msg_last_sent = now
    db.add(shop_user)

    text = shop.daily_message_text or ""
    media_path = shop.daily_message_media or ""

    if media_path and os.path.exists(media_path):
        ext = media_path.lower().split(".")[-1]
        file = FSInputFile(media_path)
        if ext in ("jpg", "jpeg", "png", "webp"):
            await message.answer_photo(photo=file, caption=text or None)
        elif ext in ("mp4", "mov", "avi"):
            await message.answer_video(video=file, caption=text or None)
        else:
            await message.answer_document(document=file, caption=text or None)
    elif text:
        await message.answer(text)
