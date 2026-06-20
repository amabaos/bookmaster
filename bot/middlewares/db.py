from typing import Any, Awaitable, Callable
from aiogram import BaseMiddleware
from db.session import AsyncSessionLocal


class DbMiddleware(BaseMiddleware):
    """Прокидывает сессию БД в data['db'] для каждого апдейта"""

    async def __call__(
        self,
        handler: Callable[[Any, dict], Awaitable[Any]],
        event: Any,
        data: dict,
    ) -> Any:
        async with AsyncSessionLocal() as session:
            data["db"] = session
            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise
