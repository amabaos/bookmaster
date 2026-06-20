import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv

load_dotenv()

from db.session import init_db
from bot.engine import start_all_shops, get_bot_and_dp
from web.routers import auth, shops, products, analytics, broadcasts, utm, crypto, wheel

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await start_all_shops()
    import asyncio
    from bot.tasks import run_trigger_broadcasts
    trigger_task = asyncio.create_task(run_trigger_broadcasts())
    yield
    trigger_task.cancel()


app = FastAPI(title="Bot Platform Admin", lifespan=lifespan)

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "dev_secret_change_me"),
    max_age=86400 * 7,
)

app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")
from bot.config import UPLOAD_DIR
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

app.include_router(auth.router)
app.include_router(shops.router)
app.include_router(products.router)
app.include_router(analytics.router)
app.include_router(broadcasts.router)
app.include_router(utm.router)
app.include_router(crypto.router)
app.include_router(wheel.router)


@app.get("/")
async def index(request: Request):
    if not request.session.get("authenticated"):
        return RedirectResponse("/login")
    return RedirectResponse("/shops/")


@app.post("/webhook/{shop_id}")
async def telegram_webhook(shop_id: int, request: Request):
    """Принимает обновления от Telegram в webhook-режиме."""
    # Проверяем секретный токен (если задан)
    if WEBHOOK_SECRET:
        token = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if token != WEBHOOK_SECRET:
            raise HTTPException(status_code=403, detail="Invalid secret token")

    entry = get_bot_and_dp(shop_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Bot not found")

    bot, dp = entry

    from aiogram.types import Update
    body = await request.body()
    try:
        update = Update.model_validate_json(body)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid update: {e}")

    await dp.feed_webhook_update(bot, update)
    return JSONResponse({"ok": True})
