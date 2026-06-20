from datetime import datetime
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, Text, BigInteger, Float, UniqueConstraint
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Shop(Base):
    """Один бот = один магазин"""
    __tablename__ = "shops"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    token_encrypted = Column(Text, nullable=False)       # токен зашифрован
    username = Column(String(255))                       # @username бота
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Тексты интерфейса
    welcome_text = Column(Text, default="Добро пожаловать! 👋")
    menu_text = Column(Text, default="Выберите раздел:")
    support_text = Column(Text, default="Напишите нам: @support")
    captcha_text = Column(Text, default="Выберите правильный смайлик 👇")

    # Крипто-настройки (общие для всех товаров магазина)
    crypto_wallet = Column(String(500), default="")
    crypto_message = Column(Text, default="Отправьте оплату на кошелёк и пришлите скриншот.")

    # Ежедневное сообщение
    daily_message_text = Column(Text, default="")
    daily_message_media = Column(String(500), default="")  # path to file

    # Фото для главного меню
    menu_photo = Column(String(500), default="")

    products = relationship("Product", back_populates="shop", cascade="all, delete-orphan")
    users = relationship("ShopUser", back_populates="shop", cascade="all, delete-orphan")
    wheel_files = relationship("WheelFile", back_populates="shop", cascade="all, delete-orphan")
    broadcasts = relationship("Broadcast", back_populates="shop", cascade="all, delete-orphan")
    events = relationship("AnalyticsEvent", back_populates="shop", cascade="all, delete-orphan")
    utm_keys = relationship("UTMKey", back_populates="shop", cascade="all, delete-orphan")
    languages = relationship("BotLanguage", back_populates="shop", cascade="all, delete-orphan")


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    shop_id = Column(Integer, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    image_path = Column(String(500), default="")
    price_usd = Column(Float, default=0.0)
    price_stars = Column(Integer, default=0)
    payment_type = Column(String(20), default="stars")  # stars / crypto / both
    stars_link = Column(String(1000), default="")       # готовая платная ссылка
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    shop = relationship("Shop", back_populates="products")
    translations = relationship("ProductTranslation", back_populates="product", cascade="all, delete-orphan")


class ShopUser(Base):
    """Пользователь конкретного магазина"""
    __tablename__ = "shop_users"

    id = Column(Integer, primary_key=True)
    shop_id = Column(Integer, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False)
    tg_id = Column(BigInteger, nullable=False)
    username = Column(String(255), default="")
    first_name = Column(String(255), default="")

    # Гейт трафика
    is_activated = Column(Boolean, default=False)   # пришёл по метке хотя бы раз
    utm_source = Column(String(255), default="")    # первая метка

    # Капча
    captcha_passed = Column(Boolean, default=False)
    captcha_round = Column(Integer, default=0)          # пройдено раундов из 3
    captcha_attempts = Column(Integer, default=0)       # полных провалов (макс 2)
    captcha_blocked_until = Column(DateTime, nullable=True)  # блок до этого времени

    # Покупки
    has_purchased = Column(Boolean, default=False)

    # Ежедневное сообщение
    daily_msg_last_sent = Column(DateTime, nullable=True)

    # Выбранный язык
    language_id = Column(Integer, ForeignKey("bot_languages.id", ondelete="SET NULL"), nullable=True)

    # Колесо фортуны
    wheel_last_spin = Column(DateTime, nullable=True)
    wheel_last_file_id = Column(Integer, nullable=True)  # чтобы не повторять подряд

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("shop_id", "tg_id", name="uq_shop_user"),)

    shop = relationship("Shop", back_populates="users")


class WheelFile(Base):
    """Файлы для колеса фортуны"""
    __tablename__ = "wheel_files"

    id = Column(Integer, primary_key=True)
    shop_id = Column(Integer, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_type = Column(String(20), default="document")  # photo / video / document
    sort_order = Column(Integer, default=0)

    shop = relationship("Shop", back_populates="wheel_files")


class CryptoOption(Base):
    """Глобальные крипто-валюты — одни для всех магазинов"""
    __tablename__ = "crypto_options"

    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), nullable=False, unique=True)   # BTC, ETH, TON …
    name = Column(String(100), default="")                     # Bitcoin, Ethereum …
    wallet_address = Column(String(500), default="")
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class UTMKey(Base):
    """Разрешённые UTM-ключи для активации бота"""
    __tablename__ = "utm_keys"

    id = Column(Integer, primary_key=True)
    shop_id = Column(Integer, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False)
    key = Column(String(255), nullable=False)       # сам ключ (уникален в рамках магазина)
    label = Column(String(255), default="")         # описание (откуда трафик)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    shop = relationship("Shop", back_populates="utm_keys")


class Broadcast(Base):
    """Рассылки"""
    __tablename__ = "broadcasts"

    id = Column(Integer, primary_key=True)
    shop_id = Column(Integer, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False)
    type = Column(String(20), default="manual")     # manual / trigger
    trigger_event = Column(String(50), default="") # started_no_purchase
    trigger_delay_hours = Column(Integer, default=24)
    text = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    shop = relationship("Shop", back_populates="broadcasts")


class AnalyticsEvent(Base):
    """События аналитики"""
    __tablename__ = "analytics_events"

    id = Column(Integer, primary_key=True)
    shop_id = Column(Integer, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False)
    tg_id = Column(BigInteger, nullable=False)
    event_type = Column(String(50), nullable=False)  # start / click_pay / purchase / wheel_spin
    utm_source = Column(String(255), default="")
    meta = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    shop = relationship("Shop", back_populates="events")


class ProductTranslation(Base):
    """Перевод товара под конкретный язык"""
    __tablename__ = "product_translations"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    language_id = Column(Integer, ForeignKey("bot_languages.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), default="")
    description = Column(Text, default="")
    image_path = Column(String(500), default="")

    __table_args__ = (UniqueConstraint("product_id", "language_id", name="uq_product_lang"),)

    product = relationship("Product", back_populates="translations")


class BotLanguage(Base):
    """Языки бота — пользователь выбирает до прохождения капчи.
    Каждый язык хранит свои версии текстов и фото меню."""
    __tablename__ = "bot_languages"

    id = Column(Integer, primary_key=True)
    shop_id = Column(Integer, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)       # Русский, English …
    flag_emoji = Column(String(10), default="")      # 🇷🇺, 🇺🇸 …
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Тексты этого языка (если пусто — используется текст из Shop)
    welcome_text = Column(Text, default="")
    menu_text = Column(Text, default="")
    menu_photo = Column(String(500), default="")
    support_text = Column(Text, default="")
    captcha_text = Column(Text, default="")

    shop = relationship("Shop", back_populates="languages")
