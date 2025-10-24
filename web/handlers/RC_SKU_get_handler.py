from aiohttp import web
import logging
from typing import Dict, Any, Optional
from decimal import Decimal

from ..middlewares import middleware, semaphore
from database.methods.RC_SKU import get_all_sku_metrics, get_sku_metrics_by_id
from database.models.RC_SKU import RC_SKU

logger = logging.getLogger(__name__)


def _serialize_sku_metric(metric: RC_SKU) -> Dict[str, Any]:
    data = {}
    
    for column in metric.__table__.columns:
        key = column.name
        value = getattr(metric, key)
        
        if isinstance(value, Decimal):
            data[key] = float(value)
        else:
            data[key] = value
            
    return data

PER_PAGE_DEFAULT = 20

@middleware(semaphore(10, 10))
async def handler(request: web.Request) -> web.Response:
    logger.debug("RC SKU get handler called")
    
    params = request.query
    db = request.app['db']
    
    if 'id' in params:
        try:
            metric_id = int(params['id'])
        except ValueError:
            return web.json_response({
                'message': 'Неверный формат ID. ID должен быть целым числом.'
            }, status=400)
            
        async with db.session as session:
            metric = await get_sku_metrics_by_id(session, metric_id)
            
            if metric:
                data = _serialize_sku_metric(metric)
                logger.info(f"Successfully fetched SKU metric by ID: {metric_id}")
                return web.json_response({
                    'fields': data
                }, status=200)
            else:
                logger.warning(f"SKU metric with ID: {metric_id} not found.")
                return web.json_response({
                    'message': f'Метрика с ID {metric_id} не найдена.'
                }, status=404)

    current_page = 1
    if 'page' in params:
        try:
            current_page = int(params['page'])
            if current_page < 1:
                current_page = 1
        except ValueError:
            return web.json_response({
                'message': 'Неверный формат страницы. Page должен быть целым числом.'
            }, status=400)
            
    async with db.session as session:
        try:
            metrics_sequence = await get_all_sku_metrics(
                session, 
                page=current_page, 
                per_page=PER_PAGE_DEFAULT
            )
            
            data_list = [_serialize_sku_metric(metric) for metric in metrics_sequence]
            
            logger.info(f"Successfully fetched page {current_page} with {len(data_list)} records.")
            return web.json_response({
                'page': current_page,
                'per_page': PER_PAGE_DEFAULT,
                'fields': data_list
            }, status=200)

        except Exception as e:
            logger.error(f"Ошибка при работе с БД в пагинации: {e}", exc_info=True)
            return web.json_response({
                'message': 'Внутренняя ошибка сервера при получении записей.'
            }, status=500)