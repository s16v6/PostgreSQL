import logging
from aiohttp import web
from decimal import Decimal
from typing import Dict, Any, Optional
from datetime import date

from ..middlewares import middleware, semaphore
from database.methods.RC_SKU import get_sku_metrics_by_id
from database.methods.RC_SKU_margin_history import create_margin_history_entry, get_latest_margin_history
from services.RC_SKU_margin_history.margin_calculator import calculate_target_margin, MARGIN_CONSTANTS # Импорт из utils

logger = logging.getLogger(__name__)

# --- ЯВНОЕ ПРЕДСТАВЛЕНИЕ ОЖИДАЕМЫХ ПАРАМЕТРОВ ---
# Обязательный параметр в любом режиме
REQUIRED_FIELDS = ['sku_id'] 
# Параметр для ручного режима ИЛИ для первого запуска в автоматическом режиме
BASE_MARGIN_FIELD = 'base_margin_percent'
# Параметр для активации автоматического режима
CALCULATE_MODE_FIELD = 'calculate'
# Опциональный параметр
OPTIONAL_FIELDS = ['date']
# ---------------------------------------------------


@middleware(semaphore(10, 10))
async def handler(request: web.Request) -> web.Response:
    """
    Веб-обработчик для расчета и сохранения целевой маржи для SKU.
    
    Использует GET-параметры: 
    - Обязательный: sku_id (int)
    - Режим (один из): base_margin_percent (float) ИЛИ calculate=true (str)
    - Опциональный: date (YYYY-MM-DD)
    """
    db = request.app['db']
    params = request.query
    
    target_date_obj: Optional[date] = None
    base_margin_percent_decimal: Optional[Decimal] = None
    is_calculate_mode = params.get(CALCULATE_MODE_FIELD, '').lower() == 'true'
    
    try:
        # 1. Проверка обязательного sku_id
        if 'sku_id' not in params:
            raise KeyError('sku_id')
        sku_id = int(params['sku_id'])

        # 2. Парсинг опциональной даты
        if 'date' in params:
            try:
                target_date_obj = date.fromisoformat(params['date'])
            except ValueError:
                # Выбрасываем исключение для обработки в блоке ValueError ниже
                raise ValueError('date_format') 

        # 3. Обработка базовой маржи в ручном режиме
        if not is_calculate_mode:
            # Ручной режим: base_margin_percent обязателен
            if BASE_MARGIN_FIELD not in params:
                raise KeyError(BASE_MARGIN_FIELD)
            
            base_margin_percent_float = float(params[BASE_MARGIN_FIELD])
            base_margin_percent_decimal = Decimal(str(base_margin_percent_float))
        
        # 3b. Парсинг base_margin_percent для первого запуска в автоматическом режиме (если предоставлен)
        elif is_calculate_mode and BASE_MARGIN_FIELD in params:
            base_margin_percent_float = float(params[BASE_MARGIN_FIELD])
            base_margin_percent_decimal = Decimal(str(base_margin_percent_float))


    except KeyError as e:
        required_params = 'sku_id (int)'
        if not is_calculate_mode:
            required_params += f' и {BASE_MARGIN_FIELD} (float)'
        return web.json_response({
            'status': 'error',
            'message': f'Необходимые параметры: {required_params}. Не передан: {e.args[0]}.'
        }, status=400)
    except ValueError as e:
        error_message = 'Неверный формат данных. sku_id должен быть целым числом, а base_margin_percent — числом (float).'
        if str(e) == 'date_format':
             error_message = 'Неверный формат даты. Используйте YYYY-MM-DD.'
        return web.json_response({
            'status': 'error',
            'message': error_message
        }, status=400)


    # 4. Получаем необходимые данные из RC_SKU
    async with db.session as session:
        sku_metric = await get_sku_metrics_by_id(session, sku_id)
        
        if not sku_metric:
            logger.warning(f"RC_SKU record with ID: {sku_id} not found for margin calculation.")
            return web.json_response({
                'status': 'error',
                'message': f'Запись RC_SKU с ID {sku_id} не найдена.'
            }, status=404)
        
        # 5. Обработка базовой маржи в автоматическом режиме
        if is_calculate_mode:
            latest_history = await get_latest_margin_history(session, sku_id)
            
            if latest_history:
                # Базовая маржа для нового расчета = Процент маржи из предыдущей записи (единое поле)
                base_margin_percent_decimal = Decimal(str(latest_history.margin_percent))
                logger.info(f"CALCULATE mode: Using history margin ({base_margin_percent_decimal}) as base margin for SKU ID {sku_id}.")
            elif base_margin_percent_decimal is not None:
                # Запасной вариант для первого запуска (нет истории)
                logger.info(f"CALCULATE mode: First run for SKU ID {sku_id}. Using provided base margin ({base_margin_percent_decimal}).")
            else:
                # Ошибка, если нет истории и не предоставлена базовая маржа для старта
                return web.json_response({
                    'status': 'error',
                    'message': f'Для SKU ID {sku_id} не найдена история маржи. Необходимо указать {BASE_MARGIN_FIELD} для первого запуска в автоматическом режиме.'
                }, status=400)
        
        # Final check
        if base_margin_percent_decimal is None:
            # Защита на случай, если логика выше не сработала
            return web.json_response({'status': 'error', 'message': 'Ошибка определения базовой маржи.'}, status=500)
            
        # 6. Выполняем расчет
        calculated_margin_decimal = calculate_target_margin(
            planned_orders_per_sku=sku_metric.planned_orders_per_sku,
            actual_orders=sku_metric.actual_orders,
            stock=sku_metric.stock,
            base_margin_percent=base_margin_percent_decimal,
            constants=MARGIN_CONSTANTS
        )

        # 7. Сохраняем результат
        # Используем обновленный метод create_margin_history_entry, который принимает только margin_percent
        new_entry = await create_margin_history_entry(
            session=session,
            sku_id=sku_id,
            margin_percent=float(calculated_margin_decimal),
            target_date=target_date_obj
        )
        
        logger.info(f"Successfully calculated and inserted margin history for SKU ID {sku_id}. Calculated margin: {calculated_margin_decimal}")
        
        return web.json_response({
            'status': 'ok',
            'id': new_entry.id,
            'margin_percent': float(calculated_margin_decimal), # Единый ключ в ответе
            'base_margin_used_for_calculation': float(base_margin_percent_decimal), # Показываем, какая маржа использовалась как база
            'target_date': new_entry.target_date.isoformat(),
            'message': f'Расчет и сохранение маржи успешно выполнено. Режим: {"Автоматический" if is_calculate_mode else "Ручной"}.'
        }, status=200)
