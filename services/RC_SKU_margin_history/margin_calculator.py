import logging
from decimal import Decimal
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Константы, заменяющие данные из 'БД SKU'
MARGIN_CONSTANTS = {
    'MAX_CAP_PERCENT': Decimal('0.25'),  
    'MIN_LEVEL_FLAG': True,             
    'MIN_LEVEL_PERCENT': Decimal('-0.10'), 
    'FIXATION_FLAG': False,             
    'FIXATION_PERCENT': Decimal('0.15'),
}


def calculate_target_margin(
    planned_orders_per_sku: int,
    actual_orders: int,
    stock: int,
    base_margin_percent: Decimal,
    constants: Dict[str, Any]
) -> Decimal:
    """
    Реализует логику расчета целевой маржи на основе соотношения Плана/Факта заказов
    и применяет ограничения из констант (Остатки, Фиксация, Нижний уровень).
    """

    # --- 1. Приоритет 1: Остатки = 0 ---
    if stock == 0:
        logger.debug("Priority 1: Stock is 0. Returning MAX_CAP_PERCENT.")
        return constants['MAX_CAP_PERCENT'] 

    # --- 2. Приоритет 2: Фиксация маржи ---
    elif constants['FIXATION_FLAG']:
        logger.debug("Priority 2: Margin fixation is ON. Returning FIXED_PERCENT.")
        return constants['FIXATION_PERCENT']

    # --- 3. Базовое изменение маржи (Формула_без_ограничения) ---
    if actual_orders < planned_orders_per_sku:
        # Маржа понижается: Процент_маржи_вчера - (План - Факт) / 100
        adjustment = Decimal(planned_orders_per_sku - actual_orders) / Decimal(100)
        formula_without_limit = base_margin_percent - adjustment
    elif actual_orders > planned_orders_per_sku:
        # Маржа повышается
        adjustment = Decimal(actual_orders - planned_orders_per_sku) / Decimal(100)
        potential_margin = base_margin_percent + adjustment
        
        # Ограничение 0.25 (Максимальный кап)
        formula_without_limit = min(potential_margin, constants['MAX_CAP_PERCENT'])
    else:
        # Факт = План, маржа не меняется
        formula_without_limit = base_margin_percent
    
    logger.debug(f"Base adjustment result (Formula_without_limit): {formula_without_limit}")

    # --- 4. Приоритет 3: Нижний уровень маржи ---
    if constants['MIN_LEVEL_FLAG']:
        if formula_without_limit < constants['MIN_LEVEL_PERCENT']:
            logger.debug(f"Priority 3: Base margin ({formula_without_limit}) is below MIN_LEVEL ({constants['MIN_LEVEL_PERCENT']}). Clamping to MIN_LEVEL.")
            return constants['MIN_LEVEL_PERCENT']
    
    # --- 5. Приоритет 4: Стандартный результат ---
    logger.debug("Priority 4: No limits triggered. Returning base adjustment result.")
    return formula_without_limit
