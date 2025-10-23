from sqlalchemy import String, Integer, Numeric, DECIMAL
from sqlalchemy.orm import Mapped, mapped_column

from database import Database

class RC_SKU(Database.BASE):
    __tablename__ = 'RC_SKU'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="Unique identifier for the metric entry")

    sku: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="SKU — SKU (Stock Keeping Unit)")

    planned_orders: Mapped[int] = mapped_column(Integer, comment="Плановое количество заказов")
    planned_orders_per_sku: Mapped[int] = mapped_column(Integer, comment="Плановое количество заказов на SKU")
    actual_orders: Mapped[int] = mapped_column(Integer, comment="Факт по заказам")
    stock: Mapped[int] = mapped_column(Integer, comment="Остатки")

    planned_margin: Mapped[float] = mapped_column(Numeric(10, 2), comment="Плановая маржа")
    margin_yesterday: Mapped[float] = mapped_column(Numeric(10, 2), comment="Маржа вчера")
    margin_week: Mapped[float] = mapped_column(Numeric(10, 2), comment="Маржа неделя")

    drr: Mapped[float] = mapped_column(Numeric(10, 4), comment="ДРР (Advertising spend share/ratio)")

    min_bid_tft: Mapped[float] = mapped_column(Numeric(10, 2), comment="Минимальная ставка ТФТ")
    bid_yesterday: Mapped[float] = mapped_column(Numeric(10, 2), comment="Ставка вчера")
    current_price: Mapped[float] = mapped_column(Numeric(10, 2), comment="Цена сейчас")
    retail_price_rp: Mapped[float] = mapped_column(Numeric(10, 2), comment="РЦ (Retail price)")

