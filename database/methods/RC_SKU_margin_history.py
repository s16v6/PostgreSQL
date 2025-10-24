import logging
from typing import Sequence, Optional
from datetime import date
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.RC_SKU_margin_history import RC_SKU_Margin_History 


logger = logging.getLogger(__name__)

PER_PAGE_DEFAULT = 20 

async def create_margin_history_entry(
    session: AsyncSession,
    sku_id: int,
    calculated_margin_percent: float,
    base_margin_percent: float,
    target_date: Optional[date] = None
) -> RC_SKU_Margin_History:
    logger.debug(f"Creating margin history entry for SKU ID: {sku_id}")
    
    new_entry = RC_SKU_Margin_History(
        sku_id=sku_id,
        calculated_margin_percent=calculated_margin_percent,
        base_margin_percent=base_margin_percent,
        # created_at будет установлено автоматически (func.current_date())
    )

    entry_data = {
        "sku_id": sku_id,
        "calculated_margin_percent": calculated_margin_percent,
        "base_margin_percent": base_margin_percent,
    }

    if target_date:
        entry_data['created_at'] = target_date
    
    new_entry = RC_SKU_Margin_History(**entry_data)
    
    session.add(new_entry)
    await session.commit()
    await session.refresh(new_entry)
    
    logger.info(f"Margin history entry created with ID: {new_entry.id}")
    return new_entry


async def get_latest_margin_history(
    session: AsyncSession,
    sku_id: int
) -> Optional[RC_SKU_Margin_History]:
    logger.debug(f"Attempting to fetch latest margin history for SKU ID: {sku_id}")
    
    stmt = (
        select(RC_SKU_Margin_History)
        .where(RC_SKU_Margin_History.sku_id == sku_id)
        .order_by(RC_SKU_Margin_History.created_at.desc()) # Сортируем по дате убыванию
        .limit(1)
    )
    
    result = await session.execute(stmt)
    
    latest_entry = result.scalars().first()
    
    if latest_entry:
        logger.info(f"Latest margin history found for SKU ID: {sku_id}, Date: {latest_entry.created_at}")
    else:
        logger.warning(f"No margin history found for SKU ID: {sku_id}")
        
    return latest_entry


async def get_margin_history_by_date(
    session: AsyncSession,
    sku_id: int,
    target_date: date
) -> Optional[RC_SKU_Margin_History]:
    logger.debug(f"Attempting to fetch margin history for SKU ID: {sku_id} on date: {target_date}")
    
    stmt = (
        select(RC_SKU_Margin_History)
        .where(RC_SKU_Margin_History.sku_id == sku_id)
        .where(RC_SKU_Margin_History.created_at == target_date)
    )
    
    result = await session.execute(stmt)
    return result.scalars().first()


async def get_all_margin_history_by_date(
    session: AsyncSession,
    target_date: date,
    page: int = 1,
    per_page: int = PER_PAGE_DEFAULT
) -> Sequence[RC_SKU_Margin_History]:
    if page < 1:
        page = 1
        
    offset = (page - 1) * per_page
    
    logger.debug(f"Fetching margin history for date {target_date}, page={page}, per_page={per_page}")
    
    stmt = (
        select(RC_SKU_Margin_History)
        .where(RC_SKU_Margin_History.created_at == target_date)
        .order_by(RC_SKU_Margin_History.sku_id)
        .limit(per_page)
        .offset(offset)
    )
    
    result = await session.execute(stmt)
    
    metrics_page = result.scalars().all()
    
    logger.debug(f"Fetched {len(metrics_page)} margin history entries for date {target_date}")
    
    return metrics_page