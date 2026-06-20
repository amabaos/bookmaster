import os, shutil, uuid
from fastapi import APIRouter, Request, Form, Depends, HTTPException, UploadFile, File
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from db.session import get_db
from db.models import Shop, Product, ShopUser, AnalyticsEvent, UTMKey, WheelFile, BotLanguage, ProductTranslation
from web.auth import require_auth
from bot.crypto import encrypt_token, decrypt_token

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))
router = APIRouter(prefix="/shops")

from bot.config import UPLOAD_DIR


def _auth(request: Request):
    require_auth(request)


def _save_upload(file: UploadFile, prefix: str) -> str:
    """Сохраняет загруженный файл, возвращает абсолютный путь."""
    ext = (file.filename or "file").split(".")[-1].lower()
    filename = f"{prefix}_{uuid.uuid4()}.{ext}"
    path = os.path.join(UPLOAD_DIR, filename)
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return path


@router.get("/", response_class=HTMLResponse)
async def shops_list(request: Request, db: AsyncSession = Depends(get_db)):
    _auth(request)
    result = await db.execute(select(Shop).order_by(Shop.created_at.desc()))
    shops = result.scalars().all()

    stats = {}
    for shop in shops:
        users_count = await db.scalar(
            select(func.count(ShopUser.id)).where(ShopUser.shop_id == shop.id)
        )
        stats[shop.id] = {"users": users_count or 0}

    from bot.engine import get_active_shop_ids
    active_ids = get_active_shop_ids()
    return templates.TemplateResponse("shops/list.html", {
        "request": request, "shops": shops, "stats": stats, "active_ids": active_ids,
    })


@router.get("/add", response_class=HTMLResponse)
async def add_shop_page(request: Request):
    _auth(request)
    return templates.TemplateResponse("shops/add.html", {"request": request, "error": None})


@router.post("/add")
async def add_shop(
    request: Request,
    name: str = Form(...),
    token: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    _auth(request)
    token = token.strip()

    import httpx
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"https://api.telegram.org/bot{token}/getMe")
    if resp.status_code != 200 or not resp.json().get("ok"):
        return templates.TemplateResponse("shops/add.html", {
            "request": request, "error": "Неверный токен бота",
        })

    bot_info = resp.json()["result"]
    shop = Shop(
        name=name,
        token_encrypted=encrypt_token(token),
        username=bot_info.get("username", ""),
    )
    db.add(shop)
    await db.commit()
    await db.refresh(shop)

    from bot.engine import start_shop
    await start_shop(shop)

    return RedirectResponse(f"/shops/{shop.id}?tab=languages", status_code=302)


@router.get("/{shop_id}", response_class=HTMLResponse)
async def shop_detail(request: Request, shop_id: int, db: AsyncSession = Depends(get_db)):
    _auth(request)
    shop = await db.get(Shop, shop_id)
    if not shop:
        raise HTTPException(404)

    result = await db.execute(
        select(Product).where(Product.shop_id == shop_id).order_by(Product.sort_order, Product.id)
    )
    products = result.scalars().all()

    utm_result = await db.execute(
        select(UTMKey).where(UTMKey.shop_id == shop_id).order_by(UTMKey.created_at)
    )
    utm_keys = utm_result.scalars().all()

    wheel_result = await db.execute(
        select(WheelFile).where(WheelFile.shop_id == shop_id).order_by(WheelFile.sort_order, WheelFile.id)
    )
    wheel_files = wheel_result.scalars().all()

    lang_result = await db.execute(
        select(BotLanguage).where(BotLanguage.shop_id == shop_id).order_by(BotLanguage.sort_order, BotLanguage.id)
    )
    languages = lang_result.scalars().all()

    # Загружаем переводы всех товаров: tr_map[product_id][language_id] = ProductTranslation
    tr_map: dict[int, dict[int, ProductTranslation]] = {}
    if products and languages:
        product_ids = [p.id for p in products]
        lang_ids = [l.id for l in languages]
        tr_result = await db.execute(
            select(ProductTranslation).where(
                ProductTranslation.product_id.in_(product_ids),
                ProductTranslation.language_id.in_(lang_ids),
            )
        )
        for tr in tr_result.scalars().all():
            tr_map.setdefault(tr.product_id, {})[tr.language_id] = tr

    return templates.TemplateResponse("shops/detail.html", {
        "request": request, "shop": shop, "products": products,
        "utm_keys": utm_keys, "wheel_files": wheel_files,
        "languages": languages, "tr_map": tr_map,
    })


@router.post("/{shop_id}/settings")
async def update_settings(
    request: Request,
    shop_id: int,
    welcome_text: str = Form(""),
    menu_text: str = Form(""),
    support_text: str = Form(""),
    captcha_text: str = Form(""),
    crypto_message: str = Form(""),
    daily_message_text: str = Form(""),
    menu_photo: UploadFile = File(None),
    db: AsyncSession = Depends(get_db),
):
    _auth(request)
    shop = await db.get(Shop, shop_id)
    if not shop:
        raise HTTPException(404)

    shop.welcome_text = welcome_text
    shop.menu_text = menu_text
    shop.support_text = support_text
    shop.captcha_text = captcha_text
    shop.crypto_message = crypto_message
    shop.daily_message_text = daily_message_text

    if menu_photo and menu_photo.filename:
        if shop.menu_photo and os.path.exists(shop.menu_photo):
            os.remove(shop.menu_photo)
        shop.menu_photo = _save_upload(menu_photo, f"menu_{shop_id}")

    await db.commit()

    from bot.engine import reload_shop
    await reload_shop(shop_id)

    return RedirectResponse(f"/shops/{shop_id}?saved=1", status_code=302)


@router.post("/{shop_id}/settings/remove_photo")
async def remove_menu_photo(request: Request, shop_id: int, db: AsyncSession = Depends(get_db)):
    _auth(request)
    shop = await db.get(Shop, shop_id)
    if not shop:
        raise HTTPException(404)
    if shop.menu_photo and os.path.exists(shop.menu_photo):
        os.remove(shop.menu_photo)
    shop.menu_photo = ""
    await db.commit()
    from bot.engine import reload_shop
    await reload_shop(shop_id)
    return RedirectResponse(f"/shops/{shop_id}?saved=1", status_code=302)


@router.post("/{shop_id}/toggle")
async def toggle_shop(request: Request, shop_id: int, db: AsyncSession = Depends(get_db)):
    _auth(request)
    shop = await db.get(Shop, shop_id)
    if not shop:
        raise HTTPException(404)
    shop.is_active = not shop.is_active
    await db.commit()

    from bot.engine import start_shop, stop_shop
    if shop.is_active:
        await start_shop(shop)
    else:
        await stop_shop(shop_id)

    return RedirectResponse(f"/shops/{shop_id}", status_code=302)


@router.post("/{shop_id}/delete")
async def delete_shop(request: Request, shop_id: int, db: AsyncSession = Depends(get_db)):
    _auth(request)
    shop = await db.get(Shop, shop_id)
    if not shop:
        raise HTTPException(404)

    from bot.engine import stop_shop
    await stop_shop(shop_id)

    await db.delete(shop)
    await db.commit()
    return RedirectResponse("/shops/", status_code=302)


# ── Языки ──────────────────────────────────────────────────────────────────

@router.post("/{shop_id}/languages/add")
async def add_language(
    request: Request,
    shop_id: int,
    name: str = Form(...),
    flag_emoji: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    _auth(request)
    shop = await db.get(Shop, shop_id)
    if not shop:
        raise HTTPException(404)
    lang = BotLanguage(shop_id=shop_id, name=name.strip(), flag_emoji=flag_emoji.strip())
    db.add(lang)
    await db.commit()
    return RedirectResponse(f"/shops/{shop_id}?tab=languages", status_code=302)


@router.post("/{shop_id}/languages/{lang_id}/settings")
async def update_language_settings(
    request: Request,
    shop_id: int,
    lang_id: int,
    name: str = Form(...),
    flag_emoji: str = Form(""),
    welcome_text: str = Form(""),
    menu_text: str = Form(""),
    support_text: str = Form(""),
    captcha_text: str = Form(""),
    menu_photo: UploadFile = File(None),
    db: AsyncSession = Depends(get_db),
):
    _auth(request)
    lang = await db.get(BotLanguage, lang_id)
    if not lang or lang.shop_id != shop_id:
        raise HTTPException(404)

    lang.name = name.strip()
    lang.flag_emoji = flag_emoji.strip()
    lang.welcome_text = welcome_text
    lang.menu_text = menu_text
    lang.support_text = support_text
    lang.captcha_text = captcha_text

    if menu_photo and menu_photo.filename:
        if lang.menu_photo and os.path.exists(lang.menu_photo):
            os.remove(lang.menu_photo)
        lang.menu_photo = _save_upload(menu_photo, f"lang_{lang_id}")

    await db.commit()

    from bot.engine import reload_shop
    await reload_shop(shop_id)

    return RedirectResponse(f"/shops/{shop_id}?tab=languages", status_code=302)


@router.post("/{shop_id}/languages/{lang_id}/remove_photo")
async def remove_language_photo(
    request: Request, shop_id: int, lang_id: int, db: AsyncSession = Depends(get_db)
):
    _auth(request)
    lang = await db.get(BotLanguage, lang_id)
    if not lang or lang.shop_id != shop_id:
        raise HTTPException(404)
    if lang.menu_photo and os.path.exists(lang.menu_photo):
        os.remove(lang.menu_photo)
    lang.menu_photo = ""
    await db.commit()
    return RedirectResponse(f"/shops/{shop_id}?tab=languages", status_code=302)


@router.post("/{shop_id}/languages/{lang_id}/toggle")
async def toggle_language(
    request: Request, shop_id: int, lang_id: int, db: AsyncSession = Depends(get_db)
):
    _auth(request)
    lang = await db.get(BotLanguage, lang_id)
    if not lang or lang.shop_id != shop_id:
        raise HTTPException(404)
    lang.is_active = not lang.is_active
    await db.commit()
    return RedirectResponse(f"/shops/{shop_id}?tab=languages", status_code=302)


@router.post("/{shop_id}/languages/{lang_id}/delete")
async def delete_language(
    request: Request, shop_id: int, lang_id: int, db: AsyncSession = Depends(get_db)
):
    _auth(request)
    lang = await db.get(BotLanguage, lang_id)
    if not lang or lang.shop_id != shop_id:
        raise HTTPException(404)
    if lang.menu_photo and os.path.exists(lang.menu_photo):
        os.remove(lang.menu_photo)
    await db.delete(lang)
    await db.commit()
    return RedirectResponse(f"/shops/{shop_id}?tab=languages", status_code=302)
