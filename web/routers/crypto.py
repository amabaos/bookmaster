from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import os

from db.session import get_db
from db.models import CryptoOption
from web.auth import require_auth

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))
router = APIRouter(prefix="/crypto")


def _auth(request: Request):
    require_auth(request)


@router.get("/", response_class=HTMLResponse)
async def crypto_list(request: Request, db: AsyncSession = Depends(get_db)):
    _auth(request)
    result = await db.execute(select(CryptoOption).order_by(CryptoOption.sort_order, CryptoOption.id))
    coins = result.scalars().all()
    return templates.TemplateResponse("crypto/index.html", {"request": request, "coins": coins})


@router.post("/add")
async def add_coin(
    request: Request,
    symbol: str = Form(...),
    name: str = Form(""),
    wallet_address: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    _auth(request)
    symbol = symbol.strip().upper()
    exists = await db.scalar(select(CryptoOption).where(CryptoOption.symbol == symbol))
    if exists:
        return RedirectResponse("/crypto/?error=duplicate", status_code=302)
    db.add(CryptoOption(symbol=symbol, name=name, wallet_address=wallet_address))
    await db.commit()
    return RedirectResponse("/crypto/", status_code=302)


@router.post("/{coin_id}/edit")
async def edit_coin(
    request: Request,
    coin_id: int,
    symbol: str = Form(...),
    name: str = Form(""),
    wallet_address: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    _auth(request)
    coin = await db.get(CryptoOption, coin_id)
    if not coin:
        raise HTTPException(404)
    coin.symbol = symbol.strip().upper()
    coin.name = name
    coin.wallet_address = wallet_address
    await db.commit()
    return RedirectResponse("/crypto/", status_code=302)


@router.post("/{coin_id}/toggle")
async def toggle_coin(request: Request, coin_id: int, db: AsyncSession = Depends(get_db)):
    _auth(request)
    coin = await db.get(CryptoOption, coin_id)
    if coin:
        coin.is_active = not coin.is_active
        await db.commit()
    return RedirectResponse("/crypto/", status_code=302)


@router.post("/{coin_id}/delete")
async def delete_coin(request: Request, coin_id: int, db: AsyncSession = Depends(get_db)):
    _auth(request)
    coin = await db.get(CryptoOption, coin_id)
    if coin:
        await db.delete(coin)
        await db.commit()
    return RedirectResponse("/crypto/", status_code=302)
