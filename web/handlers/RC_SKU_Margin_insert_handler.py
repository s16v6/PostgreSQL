from aiohttp import web
import logging
from decimal import Decimal
from typing import Dict, Any
from datetime import date # ДОБАВЛЕНО: для парсинга даты

from ..middlewares import middleware, semaphore
from database.methods.RC_SKU import get_sku_metrics_by_id
from database.methods.RC_SKU_margin_history import create_margin_history_entry

logger = logging.getLogger(__name__)

# Константы, заменяющие данные из 'БД SKU'
# В реальной системе эти константы должны извлекаться из настроек или базы данных.
MARGIN_CONSTANTS = {
    'MAX_CAP_PERCENT': Decimal('0.25'),
    'MIN_LEVEL_FLAG': True,
    'MIN_LEVEL_PERCENT': Decimal('-0.10'), 
    'FIXATION_FLAG': False,
    'FIXATION_PERCENT': Decimal('0.15'),
}


def calculate_target_margin(
    planned_orders: int,
    actual_orders: int,
    stock: int,
    base_margin_percent: Decimal,
    constants: Dict[str, Any]
) -> Decimal:
    """Реализует логику расчета целевой маржи из формулы Google Sheets."""

    # 1. Формула_без_ограничения (Base Adjustment)
    if actual_orders < planned_orders:
        # Маржа понижается: Процент_маржи_вчера - (План - Факт) / 100
        adjustment = Decimal(planned_orders - actual_orders) / Decimal(100)
        formula_without_limit = base_margin_percent - adjustment
    elif actual_orders > planned_orders:
        # Маржа повышается
        adjustment = Decimal(actual_orders - planned_orders) / Decimal(100)
        potential_margin = base_margin_percent + adjustment
        
        # Ограничение 0.25 (Максимальный кап)
        formula_without_limit = min(potential_margin, constants['MAX_CAP_PERCENT'])
    else:
        # Факт = План, маржа не меняется
        formula_without_limit = base_margin_percent
        
    
    # 2. Результат (Applying Limits)

    # Приоритет 1: Остатки = 0 (Возвращаем максимальное значение)
    if stock == 0:
        return constants['MAX_CAP_PERCENT'] 

    # Приоритет 2: Фиксация маржи
    elif constants['FIXATION_FLAG']:
        return constants['FIXATION_PERCENT']

    # Приоритет 3: Нижний уровень маржи
    elif constants['MIN_LEVEL_FLAG']:
        if formula_without_limit < constants['MIN_LEVEL_PERCENT']:
            # Если формула ниже минимального уровня, берем минимальный уровень
            return constants['MIN_LEVEL_PERCENT']
    
    # Приоритет 4: Стандартная формула (formula_without_limit)
    return formula_without_limit


@middleware(semaphore(10, 10))
async def handler(request: web.Request) -> web.Response:
    """
    Веб-обработчик для расчета и сохранения целевой маржи для SKU.
    Ожидает SKU ID, базовый процент маржи и опционально дату.
    Использует GET-параметры: sku_id, base_margin_percent и date (YYYY-MM-DD, опционально).
    """
    db = request.app['db']
    params = request.query
    
    target_date_obj = None # Объект даты, который будет передан в метод создания
    
    try:
        sku_id = int(params['sku_id'])
        # base_margin_percent - это Процент_маржи_вчера
        base_margin_percent_float = float(params['base_margin_percent'])
        # Используем Decimal для точных расчетов
        base_margin_percent_decimal = Decimal(str(base_margin_percent_float)) 

        # ДОБАВЛЕНО: Парсинг опциональной даты
        if 'date' in params:
            try:
                target_date_obj = date.fromisoformat(params['date'])
            except ValueError:
                return web.json_response({
                    'status': 'error',
                    'message': 'Неверный формат даты. Используйте YYYY-MM-DD.'
                }, status=400)
                
    except (KeyError, ValueError):
        return web.json_response({
            'status': 'error',
            'message': 'Необходимы параметры: sku_id (int) и base_margin_percent (float).'
        }, status=400)

    # 1. Получаем необходимые данные из RC_SKU
    async with db.session as session:
        sku_metric = await get_sku_metrics_by_id(session, sku_id)
        
        if not sku_metric:
            logger.warning(f"RC_SKU record with ID: {sku_id} not found for margin calculation.")
            return web.json_response({
                'status': 'error',
                'message': f'Запись RC_SKU с ID {sku_id} не найдена.'
            }, status=404)
        
        # 2. Выполняем расчет
        calculated_margin_decimal = calculate_target_margin(
            planned_orders=sku_metric.planned_orders,
            actual_orders=sku_metric.actual_orders,
            stock=sku_metric.stock,
            base_margin_percent=base_margin_percent_decimal,
            constants=MARGIN_CONSTANTS
        )

        # 3. Сохраняем результат
        new_entry = await create_margin_history_entry(
            session=session,
            sku_id=sku_id,
            calculated_margin_percent=float(calculated_margin_decimal),
            base_margin_percent=float(base_margin_percent_decimal),
            target_date=target_date_obj # ПЕРЕДАЧА ДАТЫ
        )
        
        logger.info(f"Successfully calculated and inserted margin history for SKU ID {sku_id}.")
        
        return web.json_response({
            'status': 'ok',
            'id': new_entry.id,
            'calculated_margin_percent': float(calculated_margin_decimal),
            'created_at': new_entry.created_at.isoformat(), # ДОБАВЛЕНО: Возвращаем дату в ответе
            'message': 'Расчет и сохранение маржи успешно выполнено.'
        }, status=200)
