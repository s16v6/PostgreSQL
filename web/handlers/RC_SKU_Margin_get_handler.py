import logging
from aiohttp import web
from typing import Dict, Any
from decimal import Decimal
from datetime import date, datetime

from ..middlewares import middleware, semaphore
# Импортируем новые методы для пагинации и выборки по sku_id
from database.methods.RC_SKU_margin_history import get_all_margin_history_paginated, get_all_margin_history_for_sku
from database.models.RC_SKU_margin_history import RC_SKU_Margin_History

logger = logging.getLogger(__name__)

PER_PAGE_DEFAULT = 20

def _serialize_margin_history(entry: RC_SKU_Margin_History) -> Dict[str, Any]:
    """
    Сериализует объект истории маржи для JSON-ответа, 
    конвертируя Decimal в float и date/datetime в ISO-формат.
    """
    data = {}
    
    # Сериализация по колонкам модели
    for column in entry.__table__.columns:
        key = column.name
        value = getattr(entry, key)
        
        # Конвертируем Decimal в float
        if isinstance(value, Decimal):
            data[key] = float(value)
        # Конвертируем date/datetime в ISO-формат
        elif isinstance(value, (date, datetime)):
            data[key] = value.isoformat()
        else:
            data[key] = value
            
    return data

@middleware(semaphore(10, 10))
async def handler(request: web.Request) -> web.Response:
    """
    Веб-обработчик для получения записей истории маржи.
    
    Поддерживает:
    1. Получение всей истории для конкретного SKU по параметру 'sku_id'.
    2. Получение всех записей с пагинацией по параметру 'page'.
    """
    logger.debug("RC SKU Margin get handler called")
    
    params = request.query
    db = request.app['db']
    
    # --- 1. Обработка запроса по SKU ID (Получаем всю историю для одного SKU) ---
    if 'sku_id' in params:
        try:
            sku_id = int(params['sku_id'])
        except ValueError:
            return web.json_response({
                'message': 'Неверный формат SKU ID. sku_id должен быть целым числом.'
            }, status=400)
            
        async with db.session as session:
            # Получаем всю историю для конкретного SKU
            history_sequence = await get_all_margin_history_for_sku(session, sku_id)
            
            if history_sequence:
                data_list = [_serialize_margin_history(entry) for entry in history_sequence]
                logger.info(f"Successfully fetched {len(data_list)} margin history records for SKU ID: {sku_id}")
                return web.json_response({
                    'sku_id': sku_id,
                    'fields': data_list,
                    'message': f'Найдено записей: {len(data_list)}.'
                }, status=200)
            else:
                logger.warning(f"Margin history for SKU ID: {sku_id} not found.")
                return web.json_response({
                    'message': f'История маржи для SKU ID {sku_id} не найдена.'
                }, status=404)

    # --- 2. Обработка запроса с пагинацией (Получаем все записи постранично) ---
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
            # Получаем записи с пагинацией
            history_sequence = await get_all_margin_history_paginated(
                session, 
                page=current_page, 
                per_page=PER_PAGE_DEFAULT
            )
            
            data_list = [_serialize_margin_history(entry) for entry in history_sequence]
            
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
