import os, shutil, uuid
from fastapi import APIRouter, Request, Form, Depends, HTTPException, UploadFile, File
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.session import get_db
from db.models import Shop, WheelFile
from web.auth import require_auth

router = APIRouter(prefix="/shops/{shop_id}/wheel")

from bot.config import UPLOAD_DIR


def _auth(request: Request):
    require_auth(request)


@router.post("/upload")
async def upload_wheel_file(
    request: Request,
    shop_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    _auth(request)
    shop = await db.get(Shop, shop_id)
    if not shop:
        raise HTTPException(404)

    ext = (file.filename or "file").split(".")[-1].lower()
    filename = f"wheel_{uuid.uuid4()}.{ext}"
    file_path = os.path.join(UPLOAD_DIR, filename)

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    if ext in ("jpg", "jpeg", "png", "webp", "gif"):
        file_type = "photo"
    elif ext in ("mp4", "mov", "avi", "mkv"):
        file_type = "video"
    else:
        file_type = "document"

    db.add(WheelFile(shop_id=shop_id, file_path=file_path, file_type=file_type))
    await db.commit()
    return RedirectResponse(f"/shops/{shop_id}?tab=wheel", status_code=302)


@router.post("/{file_id}/delete")
async def delete_wheel_file(
    request: Request, shop_id: int, file_id: int, db: AsyncSession = Depends(get_db)
):
    _auth(request)
    wf = await db.get(WheelFile, file_id)
    if wf and wf.shop_id == shop_id:
        if os.path.exists(wf.file_path):
            os.remove(wf.file_path)
        await db.delete(wf)
        await db.commit()
    return RedirectResponse(f"/shops/{shop_id}?tab=wheel", status_code=302)
