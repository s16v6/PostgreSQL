from sqlalchemy import String, Integer, Numeric, Date, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from database import Database

class RC_SKU_Margin_History(Database.BASE):
    __tablename__ = 'RC_SKU_margin_history'
     
    id: Mapped[int] = mapped_column(
        Integer, 
        primary_key=True, 
        comment="Уникальный идентификатор записи истории маржи"
    )
 
    sku_id: Mapped[int] = mapped_column(
        ForeignKey('RC_SKU.id', ondelete='CASCADE'), 
        nullable=False, 
        index=True,
        comment="ID записи SKU, к которой относится расчет"
    )  
    calculated_margin_percent: Mapped[float] = mapped_column(
        Numeric(10, 4), 
        nullable=False, 
        comment="Вычисленный целевой процент маржи (результат формулы)"
    )
    base_margin_percent: Mapped[float] = mapped_column(
        Numeric(10, 4), 
        nullable=False, 
        comment="Базовый процент маржи, взятый за 'вчерашний' для расчета"
    )
    created_at: Mapped[datetime] = mapped_column(
        Date,
        server_default=func.current_date(), 
        comment="Дата создания записи"
    )