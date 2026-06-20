"""Фоновые задачи: триггерные рассылки."""
import asyncio
import logging
from datetime import datetime, timedelta
from sqlalchemy import select
from db.session import AsyncSessionLocal
from db.models import ShopUser, Broadcast

logger = logging.getLogger(__name__)


async def run_trigger_broadcasts():
    """Каждые 10 минут проверяем, кому нужно отправить триггерное сообщение."""
    from bot.engine import _active_bots

    while True:
        try:
            async with AsyncSessionLocal() as db:
                # Берём все активные триггеры
                result = await db.execute(
                    select(Broadcast).where(
                        Broadcast.type == "trigger",
                        Broadcast.is_active == True,
                        Broadcast.trigger_event == "started_no_purchase",
                    )
                )
                triggers = result.scalars().all()

                for trigger in triggers:
                    if trigger.shop_id not in _active_bots:
                        continue

                    bot_obj, _, _ = _active_bots[trigger.shop_id]
                    cutoff = datetime.utcnow() - timedelta(hours=trigger.trigger_delay_hours)

                    # Пользователи: активированы, не купили, зарегистрированы до cutoff, не получали этот триггер
                    users_result = await db.execute(
                        select(ShopUser).where(
                            ShopUser.shop_id == trigger.shop_id,
                            ShopUser.is_activated == True,
                            ShopUser.has_purchased == False,
                            ShopUser.created_at <= cutoff,
                        )
                    )
                    users = users_result.scalars().all()

                    for user in users:
                        try:
                            await bot_obj.send_message(user.tg_id, trigger.text)
                        except Exception:
                            pass
                        await asyncio.sleep(0.05)  # антифлуд

        except Exception as e:
            logger.error(f"Trigger broadcast error: {e}")

        await asyncio.sleep(600)  # каждые 10 минут
