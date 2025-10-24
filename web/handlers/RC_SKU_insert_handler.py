from aiohttp import web
import logging
from typing import Dict, Any

from ..middlewares import middleware, semaphore
from database.methods.RC_SKU import create_sku_metrics

logger = logging.getLogger(__name__)


REQUIRED_FIELDS = ['sku']
OPTIONAL_FIELDS: Dict[str, Any] = {
    'planned_orders': 0,
    'planned_orders_per_sku': 0,
    'actual_orders': 0,
    'stock': 0,
    'planned_margin': 0.0,
    'margin_yesterday': 0.0,
    'margin_week': 0.0,
    'drr': 0.0,
    'min_bid_tft': 0.0,
    'bid_yesterday': 0.0,
    'current_price': 0.0,
    'retail_price_rp': 0.0

}


def _convert_value(key: str, value: str) -> Any:
    """Конвертирует строковое значение из запроса в нужный тип."""
    if key == 'sku':
        return value
    if key in ['planned_orders', 'planned_orders_per_sku', 'actual_orders', 'stock']:
        try:
            return int(value)
        except ValueError:
            raise ValueError(f"Поле '{key}' должно быть целым числом.")
    try:
        return float(value)
    except ValueError:
        raise ValueError(f"Поле '{key}' должно быть числом.")


@middleware(semaphore(10, 10))
async def handler(request: web.Request) -> web.Response:
    logger.debug("RC SKU insert handler called")
    
    try:
        params = request.query
    except Exception as e:
        logger.error(f"Ошибка при получении параметров запроса: {e}")
        return web.json_response({
            'status': 'error',
            'message': 'Неверный формат запроса'
        }, status=400)
    
    for field in REQUIRED_FIELDS:
        if field not in params:
            error_message = f"Обязательное поле '{field}' не передано."
            logger.warning(error_message)
            return web.json_response({
                'status': 'error',
                'message': error_message
            }, status=400)

    sku_metric: Dict[str, Any] = {}
    
    for key, value in params.items():
        if key in REQUIRED_FIELDS or key in OPTIONAL_FIELDS:
            try:
                sku_metric[key] = _convert_value(key, value)
            except ValueError as e:
                logger.warning(f"Ошибка конвертации значения для поля '{key}': {e}")
                return web.json_response({
                    'status': 'error',
                    'message': str(e)
                }, status=400)
        elif key not in ['id']: 
             logger.debug(f"Игнорирование неизвестного параметра: {key}")


    for field, default_value in OPTIONAL_FIELDS.items():
        if field not in sku_metric:
            sku_metric[field] = default_value
    
    db = request.app['db']
    
    try:
        async with db.session as session:
            await create_sku_metrics(session, [sku_metric]) 
        
        logger.info(f"Успешно обработан запрос на вставку для SKU: {sku_metric.get('sku')}")
        return web.json_response({
            'status': 'ok',
            'message': 'Метрика SKU успешно обработана (вставлена или пропущена, если уже существует).',
            'data': sku_metric
        }, status=200)

    except Exception as e:
        logger.error(f"Ошибка при работе с БД: {e}", exc_info=True)
        return web.json_response({
            'status': 'error',
            'message': 'Внутренняя ошибка сервера при обработке запроса к БД.'
        }, status=500)