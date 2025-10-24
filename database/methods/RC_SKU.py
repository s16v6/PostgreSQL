from typing import List, Dict, Any, Optional, Sequence
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.engine import Result, ScalarResult

from database.models.RC_SKU import RC_SKU

logger = logging.getLogger(__name__)

async def create_sku_metrics(session: AsyncSession, metrics_list: List[Dict[str, Any]]):
    logger.debug(f"Preparing to insert {len(metrics_list)} SKU metrics")
    metrics_to_add = []
    
    for item in metrics_list:
        sku_to_check = item.get('sku')

        if sku_to_check:
            stmt = select(RC_SKU).where(RC_SKU.sku == sku_to_check)
            result = await session.execute(stmt)
            existing_metric = result.scalars().first()
            
            if existing_metric:
                logger.debug(f"Metric for SKU '{sku_to_check}' already exists, skipping")
                continue
        
        item.pop('id', None)
        
        db_metric = RC_SKU(**item)
        metrics_to_add.append(db_metric)
            
    if metrics_to_add:
        session.add_all(metrics_to_add)
        await session.commit()
        logger.debug(f"Successfully added {len(metrics_to_add)} new SKU metrics")
    else:
        logger.debug("No new SKU metrics to add")

async def get_all_sku_metrics(session: AsyncSession,
                            page: int = 1,
                            per_page: int = 20,) -> Sequence[RC_SKU]:
    if page < 1:
        page = 1
    offset = (page - 1) * per_page

    logger.debug(
        f"Attempting to fetch SKU metrics: page={page}, per_page={per_page}, offset={offset}"
    )

    stmt = select(RC_SKU).limit(per_page).offset(offset)
    result: Result = await session.execute(stmt)
    metrics_page: Sequence[RC_SKU] = result.scalars().all()

    logger.debug(f"Successfully fetched {len(metrics_page)} SKU metrics for page {page}")

    return metrics_page



async def get_sku_metrics_by_id(session: AsyncSession, id: int) -> Optional[RC_SKU]:
    logger.debug(f"Attempting to fetch SKU metric with ID: {id}")
    
    stmt = select(RC_SKU).where(RC_SKU.id == id)
    
    result: Result = await session.execute(stmt)
    
    sku_metric: Optional[RC_SKU] = result.scalars().first()
        
    return sku_metric