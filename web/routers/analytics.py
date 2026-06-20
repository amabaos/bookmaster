import io, csv
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import os

from db.session import get_db
from db.models import Shop, ShopUser, AnalyticsEvent, BotLanguage
from web.auth import require_auth

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))
router = APIRouter(prefix="/shops/{shop_id}/analytics")


def _auth(request: Request):
    require_auth(request)


@router.get("/", response_class=HTMLResponse)
async def analytics(request: Request, shop_id: int, db: AsyncSession = Depends(get_db)):
    _auth(request)
    shop = await db.get(Shop, shop_id)
    if not shop:
        raise HTTPException(404)

    since = datetime.utcnow() - timedelta(days=30)

    total_users = await db.scalar(
        select(func.count(ShopUser.id)).where(ShopUser.shop_id == shop_id)
    )
    activated_users = await db.scalar(
        select(func.count(ShopUser.id)).where(
            ShopUser.shop_id == shop_id, ShopUser.is_activated == True
        )
    )
    captcha_passed_count = await db.scalar(
        select(func.count(ShopUser.id)).where(
            ShopUser.shop_id == shop_id, ShopUser.captcha_passed == True
        )
    )
    blocked_count = await db.scalar(
        select(func.count(ShopUser.id)).where(
            ShopUser.shop_id == shop_id,
            ShopUser.captcha_blocked_until > datetime.utcnow(),
        )
    )
    total_starts = await db.scalar(
        select(func.count(AnalyticsEvent.id)).where(
            AnalyticsEvent.shop_id == shop_id,
            AnalyticsEvent.event_type == "start",
        )
    )
    total_clicks = await db.scalar(
        select(func.count(AnalyticsEvent.id)).where(
            AnalyticsEvent.shop_id == shop_id,
            AnalyticsEvent.event_type == "click_pay",
        )
    )

    # UTM источники
    utm_result = await db.execute(
        select(AnalyticsEvent.utm_source, func.count(AnalyticsEvent.id))
        .where(AnalyticsEvent.shop_id == shop_id, AnalyticsEvent.event_type == "start")
        .group_by(AnalyticsEvent.utm_source)
        .order_by(func.count(AnalyticsEvent.id).desc())
    )
    utm_stats = utm_result.all()

    # По дням (последние 14 дней)
    days_data = []
    for i in range(13, -1, -1):
        day_start = datetime.utcnow().replace(hour=0, minute=0, second=0) - timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        count = await db.scalar(
            select(func.count(AnalyticsEvent.id)).where(
                AnalyticsEvent.shop_id == shop_id,
                AnalyticsEvent.event_type == "start",
                AnalyticsEvent.created_at >= day_start,
                AnalyticsEvent.created_at < day_end,
            )
        )
        days_data.append({"date": day_start.strftime("%d.%m"), "starts": count or 0})

    # Статистика по языкам
    lang_result = await db.execute(
        select(BotLanguage).where(BotLanguage.shop_id == shop_id)
    )
    languages = {l.id: l for l in lang_result.scalars().all()}

    lang_counts_result = await db.execute(
        select(ShopUser.language_id, func.count(ShopUser.id))
        .where(ShopUser.shop_id == shop_id, ShopUser.is_activated == True)
        .group_by(ShopUser.language_id)
        .order_by(func.count(ShopUser.id).desc())
    )
    raw_lang = lang_counts_result.all()

    lang_stats = []
    total_with_lang = sum(c for _, c in raw_lang)
    for lang_id, count in raw_lang:
        lang = languages.get(lang_id) if lang_id else None
        pct = round(count / total_with_lang * 100) if total_with_lang else 0
        lang_stats.append({
            "name": lang.name if lang else "Не выбран",
            "flag": lang.flag_emoji if lang else "—",
            "count": count,
            "pct": pct,
        })

    conversion = round((total_clicks / total_starts * 100), 1) if total_starts else 0

    return templates.TemplateResponse("analytics/index.html", {
        "request": request,
        "shop": shop,
        "total_users": total_users or 0,
        "activated_users": activated_users or 0,
        "captcha_passed_count": captcha_passed_count or 0,
        "blocked_count": blocked_count or 0,
        "total_starts": total_starts or 0,
        "total_clicks": total_clicks or 0,
        "conversion": conversion,
        "utm_stats": utm_stats,
        "days_data": days_data,
        "lang_stats": lang_stats,
    })


@router.get("/export/users")
async def export_users(request: Request, shop_id: int, db: AsyncSession = Depends(get_db)):
    _auth(request)
    shop = await db.get(Shop, shop_id)
    if not shop:
        raise HTTPException(404)

    lang_result = await db.execute(select(BotLanguage).where(BotLanguage.shop_id == shop_id))
    lang_map = {l.id: f"{l.flag_emoji} {l.name}".strip() for l in lang_result.scalars().all()}

    result = await db.execute(
        select(ShopUser).where(ShopUser.shop_id == shop_id).order_by(ShopUser.created_at.desc())
    )
    users = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["tg_id", "username", "first_name", "utm_source", "language",
                     "captcha_passed", "captcha_blocked_until", "has_purchased", "created_at"])
    for u in users:
        lang_name = lang_map.get(u.language_id, "") if u.language_id else ""
        writer.writerow([u.tg_id, u.username, u.first_name, u.utm_source, lang_name,
                         u.captcha_passed, u.captcha_blocked_until, u.has_purchased, u.created_at])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=users_{shop_id}.csv"},
    )
