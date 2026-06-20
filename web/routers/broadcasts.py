from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import os

from db.session import get_db
from db.models import Shop, ShopUser, Broadcast
from web.auth import require_auth

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))
router = APIRouter(prefix="/shops/{shop_id}/broadcasts")


def _auth(request: Request):
    require_auth(request)


@router.get("/", response_class=HTMLResponse)
async def broadcasts_page(request: Request, shop_id: int, db: AsyncSession = Depends(get_db)):
    _auth(request)
    shop = await db.get(Shop, shop_id)
    if not shop:
        raise HTTPException(404)

    result = await db.execute(
        select(Broadcast).where(Broadcast.shop_id == shop_id).order_by(Broadcast.created_at.desc())
    )
    broadcasts = result.scalars().all()

    return templates.TemplateResponse("broadcasts/index.html", {
        "request": request, "shop": shop, "broadcasts": broadcasts,
    })


@router.post("/send")
async def send_broadcast(
    request: Request,
    shop_id: int,
    text: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    _auth(request)
    shop = await db.get(Shop, shop_id)
    if not shop:
        raise HTTPException(404)

    # Сохраняем рассылку
    broadcast = Broadcast(shop_id=shop_id, type="manual", text=text)
    db.add(broadcast)
    await db.commit()

    # Рассылаем
    from bot.engine import _active_bots
    from bot.crypto import decrypt_token
    from aiogram import Bot

    if shop_id not in _active_bots:
        return RedirectResponse(f"/shops/{shop_id}/broadcasts/?sent=error", status_code=302)

    bot_obj, _, _ = _active_bots[shop_id]

    result = await db.execute(
        select(ShopUser).where(ShopUser.shop_id == shop_id, ShopUser.is_activated == True)
    )
    users = result.scalars().all()

    sent = 0
    for user in users:
        try:
            await bot_obj.send_message(user.tg_id, text)
            sent += 1
        except Exception:
            pass

    return RedirectResponse(f"/shops/{shop_id}/broadcasts/?sent={sent}", status_code=302)


@router.post("/trigger/add")
async def add_trigger(
    request: Request,
    shop_id: int,
    text: str = Form(...),
    trigger_delay_hours: int = Form(24),
    db: AsyncSession = Depends(get_db),
):
    _auth(request)
    broadcast = Broadcast(
        shop_id=shop_id,
        type="trigger",
        trigger_event="started_no_purchase",
        trigger_delay_hours=trigger_delay_hours,
        text=text,
    )
    db.add(broadcast)
    await db.commit()
    return RedirectResponse(f"/shops/{shop_id}/broadcasts/", status_code=302)


@router.post("/trigger/{broadcast_id}/delete")
async def delete_trigger(
    request: Request, shop_id: int, broadcast_id: int, db: AsyncSession = Depends(get_db)
):
    _auth(request)
    b = await db.get(Broadcast, broadcast_id)
    if b and b.shop_id == shop_id:
        await db.delete(b)
        await db.commit()
    return RedirectResponse(f"/shops/{shop_id}/broadcasts/", status_code=302)
