import os, shutil, uuid
from fastapi import APIRouter, Request, Form, Depends, HTTPException, UploadFile, File
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.session import get_db
from db.models import Shop, Product, ProductTranslation
from web.auth import require_auth

router = APIRouter(prefix="/shops/{shop_id}/products")

from bot.config import UPLOAD_DIR


def _auth(request: Request):
    require_auth(request)


def _save_upload(file: UploadFile, prefix: str) -> str:
    ext = (file.filename or "file").split(".")[-1].lower()
    filename = f"{prefix}_{uuid.uuid4()}.{ext}"
    path = os.path.join(UPLOAD_DIR, filename)
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return path


@router.post("/add")
async def add_product(
    request: Request,
    shop_id: int,
    name: str = Form(...),
    description: str = Form(""),
    price_usd: float = Form(0.0),
    price_stars: int = Form(0),
    payment_type: str = Form("stars"),
    stars_link: str = Form(""),
    image: UploadFile = File(None),
    db: AsyncSession = Depends(get_db),
):
    _auth(request)
    shop = await db.get(Shop, shop_id)
    if not shop:
        raise HTTPException(404)

    image_path = ""
    if image and image.filename:
        image_path = _save_upload(image, f"product_{shop_id}")

    product = Product(
        shop_id=shop_id, name=name, description=description,
        price_usd=price_usd, price_stars=price_stars,
        payment_type=payment_type, stars_link=stars_link, image_path=image_path,
    )
    db.add(product)
    await db.commit()
    return RedirectResponse(f"/shops/{shop_id}?tab=products", status_code=302)


@router.post("/{product_id}/delete")
async def delete_product(
    request: Request, shop_id: int, product_id: int, db: AsyncSession = Depends(get_db)
):
    _auth(request)
    product = await db.get(Product, product_id)
    if not product or product.shop_id != shop_id:
        raise HTTPException(404)
    if product.image_path and os.path.exists(product.image_path):
        os.remove(product.image_path)
    await db.delete(product)
    await db.commit()
    return RedirectResponse(f"/shops/{shop_id}?tab=products", status_code=302)


@router.post("/{product_id}/edit")
async def edit_product(
    request: Request,
    shop_id: int,
    product_id: int,
    name: str = Form(...),
    description: str = Form(""),
    price_usd: float = Form(0.0),
    price_stars: int = Form(0),
    payment_type: str = Form("stars"),
    stars_link: str = Form(""),
    image: UploadFile = File(None),
    db: AsyncSession = Depends(get_db),
):
    _auth(request)
    product = await db.get(Product, product_id)
    if not product or product.shop_id != shop_id:
        raise HTTPException(404)

    product.name = name
    product.description = description
    product.price_usd = price_usd
    product.price_stars = price_stars
    product.payment_type = payment_type
    product.stars_link = stars_link

    if image and image.filename:
        if product.image_path and os.path.exists(product.image_path):
            os.remove(product.image_path)
        product.image_path = _save_upload(image, f"product_{shop_id}")

    await db.commit()
    return RedirectResponse(f"/shops/{shop_id}?tab=products", status_code=302)


# ── Переводы товаров ───────────────────────────────────────────────────────

@router.post("/{product_id}/translations/{lang_id}/save")
async def save_translation(
    request: Request,
    shop_id: int,
    product_id: int,
    lang_id: int,
    name: str = Form(""),
    description: str = Form(""),
    image: UploadFile = File(None),
    db: AsyncSession = Depends(get_db),
):
    _auth(request)
    product = await db.get(Product, product_id)
    if not product or product.shop_id != shop_id:
        raise HTTPException(404)

    result = await db.execute(
        select(ProductTranslation).where(
            ProductTranslation.product_id == product_id,
            ProductTranslation.language_id == lang_id,
        )
    )
    tr = result.scalar_one_or_none()

    if tr is None:
        tr = ProductTranslation(product_id=product_id, language_id=lang_id)
        db.add(tr)

    tr.name = name
    tr.description = description

    if image and image.filename:
        if tr.image_path and os.path.exists(tr.image_path):
            os.remove(tr.image_path)
        tr.image_path = _save_upload(image, f"tr_{product_id}_{lang_id}")

    await db.commit()
    return RedirectResponse(f"/shops/{shop_id}?tab=products", status_code=302)


@router.post("/{product_id}/translations/{lang_id}/remove_image")
async def remove_translation_image(
    request: Request, shop_id: int, product_id: int, lang_id: int,
    db: AsyncSession = Depends(get_db),
):
    _auth(request)
    result = await db.execute(
        select(ProductTranslation).where(
            ProductTranslation.product_id == product_id,
            ProductTranslation.language_id == lang_id,
        )
    )
    tr = result.scalar_one_or_none()
    if tr:
        if tr.image_path and os.path.exists(tr.image_path):
            os.remove(tr.image_path)
        tr.image_path = ""
        await db.commit()
    return RedirectResponse(f"/shops/{shop_id}?tab=products", status_code=302)
