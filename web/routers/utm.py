from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.session import get_db
from db.models import UTMKey
from web.auth import require_auth

router = APIRouter(prefix="/shops/{shop_id}/utm")


def _auth(request: Request):
    require_auth(request)


@router.post("/add")
async def add_key(
    request: Request,
    shop_id: int,
    key: str = Form(...),
    label: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    _auth(request)
    key = key.strip().lower().replace(" ", "_")

    # Проверяем уникальность
    exists = await db.scalar(
        select(UTMKey).where(UTMKey.shop_id == shop_id, UTMKey.key == key)
    )
    if exists:
        return RedirectResponse(f"/shops/{shop_id}?tab=links&error=duplicate", status_code=302)

    db.add(UTMKey(shop_id=shop_id, key=key, label=label))
    await db.commit()
    return RedirectResponse(f"/shops/{shop_id}?tab=links", status_code=302)


@router.post("/{key_id}/delete")
async def delete_key(
    request: Request, shop_id: int, key_id: int, db: AsyncSession = Depends(get_db)
):
    _auth(request)
    utm_key = await db.get(UTMKey, key_id)
    if utm_key and utm_key.shop_id == shop_id:
        await db.delete(utm_key)
        await db.commit()
    return RedirectResponse(f"/shops/{shop_id}?tab=links", status_code=302)


@router.post("/{key_id}/toggle")
async def toggle_key(
    request: Request, shop_id: int, key_id: int, db: AsyncSession = Depends(get_db)
):
    _auth(request)
    utm_key = await db.get(UTMKey, key_id)
    if utm_key and utm_key.shop_id == shop_id:
        utm_key.is_active = not utm_key.is_active
        await db.commit()
    return RedirectResponse(f"/shops/{shop_id}?tab=links", status_code=302)
