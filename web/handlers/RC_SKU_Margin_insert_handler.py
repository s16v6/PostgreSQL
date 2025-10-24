import logging
from aiohttp import web
from decimal import Decimal
from typing import Dict, Any, Optional
from datetime import date

from ..middlewares import middleware, semaphore
from database.methods.RC_SKU import get_sku_metrics_by_id
from database.methods.RC_SKU_margin_history import create_margin_history_entry, get_latest_margin_history
# Импорт из utils/services (подтверждено, что используется только в calculate=true)
from services.RC_SKU_margin_history.margin_calculator import calculate_target_margin, MARGIN_CONSTANTS 

logger = logging.getLogger(__name__)

# --- ЯВНОЕ ПРЕДСТАВЛЕНИЕ ОЖИДАЕМЫХ ПАРАМЕТРОВ ---
# Обязательный параметр в любом режиме
REQUIRED_FIELDS = ['sku_id'] 
# Параметр для ручного ввода ИЛИ для первого запуска авторасчета.
INPUT_MARGIN_FIELD = 'margin_percent' 
# Параметр для активации автоматического режима
CALCULATE_MODE_FIELD = 'calculate'
# Опциональный параметр
OPTIONAL_FIELDS = ['date']
# ---------------------------------------------------


@middleware(semaphore(10, 10))
async def handler(request: web.Request) -> web.Response:
    """
    Веб-обработчик для сохранения или расчета целевой маржи для SKU.
    
    Использует GET-параметры: 
    - Обязательный: sku_id (int)
    - Режим (один из): margin_percent (float) ИЛИ calculate=true (str)
    - Опциональный: date (YYYY-MM-DD)
    """
    db = request.app['db']
    params = request.query
    
    target_date_obj: Optional[date] = None
    # Это переменная будет хранить либо входное значение, либо рассчитанное.
    final_margin_decimal: Optional[Decimal] = None 
    # Используем input_or_base_margin_decimal для хранения входящего значения (margin_percent)
    input_or_base_margin_decimal: Optional[Decimal] = None 
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
                raise ValueError('date_format') 

        # 3. Парсинг входной маржи (margin_percent)
        if INPUT_MARGIN_FIELD in params:
            input_margin_float = float(params[INPUT_MARGIN_FIELD])
            input_or_base_margin_decimal = Decimal(str(input_margin_float))
        
        # 4. Проверка обязательного наличия входной маржи для ручного режима
        if not is_calculate_mode and input_or_base_margin_decimal is None:
             raise KeyError(INPUT_MARGIN_FIELD)


    except KeyError as e:
        required_params = 'sku_id (int)'
        if not is_calculate_mode:
            required_params += f' и {INPUT_MARGIN_FIELD} (float)'
        return web.json_response({
            'status': 'error',
            'message': f'Необходимые параметры: {required_params}. Не передан: {e.args[0]}.'
        }, status=400)
    except ValueError as e:
        error_message = 'Неверный формат данных. sku_id должен быть целым числом, а margin_percent — числом (float).'
        if str(e) == 'date_format':
             error_message = 'Неверный формат даты. Используйте YYYY-MM-DD.'
        return web.json_response({
            'status': 'error',
            'message': error_message
        }, status=400)


    # --- ЛОГИКА РУЧНОГО ИЛИ АВТОМАТИЧЕСКОГО РЕЖИМА ---
    
    if not is_calculate_mode:
        # 5. РУЧНОЙ РЕЖИМ: Просто сохраняем значение из запроса
        final_margin_decimal = input_or_base_margin_decimal
        logger.info(f"MANUAL mode: Preparing to save provided margin ({final_margin_decimal}) for SKU ID {sku_id}.")

    else:
        # 5. АВТОМАТИЧЕСКИЙ РЕЖИМ: Получаем данные и рассчитываем
        async with db.session as session:
            # 5a. Получаем необходимые данные из RC_SKU
            sku_metric = await get_sku_metrics_by_id(session, sku_id)
            
            if not sku_metric:
                logger.warning(f"RC_SKU record with ID: {sku_id} not found for margin calculation.")
                return web.json_response({
                    'status': 'error',
                    'message': f'Запись RC_SKU с ID {sku_id} не найдена.'
                }, status=404)

            # 5b. Определяем базовую маржу для расчета (из истории или из input)
            latest_history = await get_latest_margin_history(session, sku_id)
            base_margin_percent_for_calc: Optional[Decimal] = None
            
            if latest_history:
                # Берем маржу из самой свежей записи в истории
                base_margin_percent_for_calc = Decimal(str(latest_history.margin_percent))
                logger.info(f"CALCULATE mode: Using history margin ({base_margin_percent_for_calc}) as base for SKU ID {sku_id}.")
            elif input_or_base_margin_decimal is not None:
                # Если истории нет, используем маржу, пришедшую в запросе
                base_margin_percent_for_calc = input_or_base_margin_decimal
                logger.info(f"CALCULATE mode: First run. Using input margin ({base_margin_percent_for_calc}) as base.")
            else:
                return web.json_response({
                    'status': 'error',
                    'message': f'Для SKU ID {sku_id} не найдена история. Необходимо указать {INPUT_MARGIN_FIELD} для старта авторасчета.'
                }, status=400)
            
            # 6. Выполняем расчет с использованием planned_orders_per_sku
            final_margin_decimal = calculate_target_margin(
                planned_orders_per_sku=sku_metric.planned_orders_per_sku, 
                actual_orders=sku_metric.actual_orders,
                stock=sku_metric.stock,
                base_margin_percent=base_margin_percent_for_calc,
                constants=MARGIN_CONSTANTS
            )
            logger.info(f"Calculation completed. Final margin: {final_margin_decimal}")

    # 7. Финальная проверка перед сохранением
    if final_margin_decimal is None:
         return web.json_response({'status': 'error', 'message': 'Критическая ошибка: не удалось определить итоговую маржу.'}, status=500)
    
    # 8. Сохраняем результат в БД (Единый блок для обоих режимов)
    async with db.session as session:
        new_entry = await create_margin_history_entry(
            session=session,
            sku_id=sku_id,
            margin_percent=float(final_margin_decimal),
            target_date=target_date_obj
        )
    
        logger.info(f"Successfully inserted margin history for SKU ID {sku_id}. Final margin: {final_margin_decimal}")
        
        # 9. Ответ
        return web.json_response({
            'status': 'ok',
            'id': new_entry.id,
            'margin_percent': float(final_margin_decimal), # Фактический результат, сохраненный в БД
            'target_date': new_entry.target_date.isoformat(),
            'message': f'Маржа успешно сохранена. Режим: {"Автоматический" if is_calculate_mode else "Ручной"}.'
        }, status=200)