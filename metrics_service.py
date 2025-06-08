"""
Сервис для обработки метрик продаж
"""
import logging
from typing import Dict, Any, List
from datetime import date, datetime

from models import Manager, DailyMetrics, Transaction, ActionType, ProductType
from gpt_parser import gpt_parser

logger = logging.getLogger(__name__)


class MetricsService:
    """Сервис для обработки и агрегации метрик продаж"""
    
    async def process_manager_message(self, manager: Manager, message: str) -> Dict[str, Any]:
        """
        Обработка сообщения менеджера
        
        Args:
            manager: Менеджер
            message: Сообщение для обработки
            
        Returns:
            Результат обработки с подтверждением
        """
        try:
            # Парсинг сообщения через GPT
            parsed_data = await gpt_parser.parse_message(message)
            
            if not parsed_data:
                return {
                    "success": False,
                    "error": "Не удалось распарсить сообщение",
                    "confirmation": "❌ Не удалось понять сообщение. Попробуйте переформулировать."
                }
            
            # Создание транзакции
            transaction = await Transaction.create(
                manager=manager,
                raw_message=message,
                action_type=parsed_data["action_type"],
                client_name=parsed_data.get("client_name"),
                is_new_client=parsed_data.get("is_new_client"),
                products=parsed_data.get("products", []),
                amount=parsed_data.get("amount"),
                count=parsed_data.get("count", 1),
                parsed_data=parsed_data
            )
            
            # Обновление дневных метрик
            await self.update_daily_metrics(manager, parsed_data)
            
            # Отметка транзакции как обработанной
            transaction.processed = True
            await transaction.save()
            
            # Формирование подтверждения
            confirmation = gpt_parser.format_confirmation(parsed_data)
            
            logger.info(f"Обработано сообщение от {manager.full_name}: {parsed_data['action_type']}")
            
            return {
                "success": True,
                "parsed_data": parsed_data,
                "confirmation": f"✅ Записано!\n{confirmation}",
                "transaction_id": transaction.id
            }
            
        except Exception as e:
            logger.error(f"Ошибка обработки сообщения: {e}")
            return {
                "success": False,
                "error": str(e),
                "confirmation": "❌ Произошла ошибка при обработке. Попробуйте еще раз."
            }
    
    async def update_daily_metrics(self, manager: Manager, parsed_data: Dict[str, Any]) -> None:
        """
        Обновление дневных метрик на основе распарсенных данных
        
        Args:
            manager: Менеджер
            parsed_data: Распарсенные данные от GPT
        """
        metrics = await DailyMetrics.get_or_create_today(manager)
        
        action_type = parsed_data["action_type"]
        amount = parsed_data.get("amount", 0) or 0
        count = parsed_data.get("count", 1)
        is_new_client = parsed_data.get("is_new_client")
        products = parsed_data.get("products", [])
        
        # Обновление метрик в зависимости от типа действия
        if action_type == ActionType.NEW_PURCHASE:
            metrics.new_clients += count
            metrics.newcomers_purchased += count
            metrics.total_revenue += amount
            metrics.newcomer_revenue += amount
            
        elif action_type == ActionType.RENEWAL:
            metrics.active_clients += count
            metrics.clients_renewed += count
            metrics.total_revenue += amount
            
        elif action_type == ActionType.REJECTION:
            metrics.rejections += count
            
        elif action_type == ActionType.BONUS:
            metrics.bonuses_given += count
            
        elif action_type == ActionType.REVIEW:
            metrics.reviews_received += count
            
        elif action_type == ActionType.CONTACT:
            if is_new_client:
                metrics.newcomers_contacted += count
            
        elif action_type == ActionType.SMS:
            metrics.sms_silent_clients += count
            
        elif action_type == ActionType.RENEWAL_MESSAGE:
            metrics.renewal_messages_sent += count
            
        elif action_type == ActionType.DIALOG:
            metrics.total_dialogs += count
        
        # Обновление продуктовых метрик
        await self._update_product_metrics(metrics, products, count)
        
        await metrics.save()
        logger.info(f"Обновлены метрики для {manager.full_name}: {action_type}")
    
    async def _update_product_metrics(self, metrics: DailyMetrics, products: List[str], count: int) -> None:
        """
        Обновление метрик по продуктам
        
        Args:
            metrics: Объект метрик
            products: Список продуктов
            count: Количество продаж
        """
        # Проверка на связки продуктов
        if len(products) > 1:
            sorted_products = sorted(products)
            
            if ProductType.MPSTATS in sorted_products and ProductType.MARKETGURU in sorted_products:
                metrics.mpstats_marketguru_sold += count
            elif ProductType.MPSTATS in sorted_products and ProductType.WILDBERRIES in sorted_products:
                metrics.mpstats_wildberries_sold += count
            elif ProductType.MPSTATS in sorted_products and ProductType.MANIPLACE in sorted_products:
                metrics.mpstats_maniplace_sold += count
        
        # Обновление единичных продуктов
        for product in products:
            if product == ProductType.MPSTATS:
                metrics.mpstats_sold += count
            elif product == ProductType.WILDBERRIES:
                metrics.wildberries_sold += count
            elif product == ProductType.MARKETGURU:
                metrics.marketguru_sold += count
            elif product == ProductType.MANIPLACE:
                metrics.maniplace_sold += count
    
    async def get_manager_stats_today(self, manager: Manager) -> Dict[str, Any]:
        """
        Получение статистики менеджера за сегодня
        
        Args:
            manager: Менеджер
            
        Returns:
            Словарь со статистикой
        """
        metrics = await DailyMetrics.get_or_create_today(manager)
        
        return {
            "date": date.today().strftime("%Y-%m-%d"),
            "manager": manager.full_name,
            "total_dialogs": metrics.total_dialogs,
            "new_clients": metrics.new_clients,
            "active_clients": metrics.active_clients,
            "total_revenue": metrics.total_revenue,
            "newcomer_revenue": metrics.newcomer_revenue,
            "rejections": metrics.rejections,
            "reviews": metrics.reviews_received,
            "bonuses": metrics.bonuses_given,
            "products": {
                "mpstats": metrics.mpstats_sold,
                "wildberries": metrics.wildberries_sold,
                "marketguru": metrics.marketguru_sold,
                "maniplace": metrics.maniplace_sold,
                "combos": {
                    "mpstats_marketguru": metrics.mpstats_marketguru_sold,
                    "mpstats_wildberries": metrics.mpstats_wildberries_sold,
                    "mpstats_maniplace": metrics.mpstats_maniplace_sold
                }
            }
        }
    
    async def format_daily_stats(self, manager: Manager) -> str:
        """
        Форматирование дневной статистики для отправки менеджеру
        
        Args:
            manager: Менеджер
            
        Returns:
            Отформатированная строка со статистикой
        """
        stats = await self.get_manager_stats_today(manager)
        
        text = f"📊 Ваша статистика за {stats['date']}:\n\n"
        
        # Основные метрики
        text += "🎯 Основные показатели:\n"
        text += f"• Всего диалогов: {stats['total_dialogs']}\n"
        text += f"• Новых клиентов: {stats['new_clients']}\n"
        text += f"• Активных клиентов: {stats['active_clients']}\n"
        text += f"• Отказов: {stats['rejections']}\n"
        text += f"• Отзывов: {stats['reviews']}\n"
        text += f"• Бонусов выдано: {stats['bonuses']}\n\n"
        
        # Финансы
        text += "💰 Финансовые показатели:\n"
        text += f"• Общая выручка: {stats['total_revenue']:,.0f}₽\n"
        text += f"• Выручка от новичков: {stats['newcomer_revenue']:,.0f}₽\n\n"
        
        # Продукты
        products = stats['products']
        if any(products[p] > 0 for p in ['mpstats', 'wildberries', 'marketguru', 'maniplace']):
            text += "📦 Продукты:\n"
            if products['mpstats'] > 0:
                text += f"• МПСтатс: {products['mpstats']}\n"
            if products['wildberries'] > 0:
                text += f"• Вайлдберрис: {products['wildberries']}\n"
            if products['marketguru'] > 0:
                text += f"• Маркетгуру: {products['marketguru']}\n"
            if products['maniplace'] > 0:
                text += f"• Маниплейс: {products['maniplace']}\n"
        
        # Связки
        combos = products['combos']
        if any(combos[c] > 0 for c in combos):
            text += "\n🔗 Связки продуктов:\n"
            if combos['mpstats_marketguru'] > 0:
                text += f"• МПСтатс + Маркетгуру: {combos['mpstats_marketguru']}\n"
            if combos['mpstats_wildberries'] > 0:
                text += f"• МПСтатс + Вайлдберрис: {combos['mpstats_wildberries']}\n"
            if combos['mpstats_maniplace'] > 0:
                text += f"• МПСтатс + Маниплейс: {combos['mpstats_maniplace']}\n"
        
        return text
    
    async def get_all_managers_metrics_today(self) -> List[DailyMetrics]:
        """
        Получение метрик всех менеджеров за сегодня
        
        Returns:
            Список объектов DailyMetrics за сегодня
        """
        today = date.today()
        return await DailyMetrics.filter(date=today).prefetch_related('manager')
    
    async def reset_manager_metrics(self, manager: Manager) -> bool:
        """
        Сброс метрик менеджера за сегодня (для отладки)
        
        Args:
            manager: Менеджер
            
        Returns:
            True если успешно
        """
        try:
            today = date.today()
            metrics = await DailyMetrics.get_or_none(manager=manager, date=today)
            
            if metrics:
                await metrics.delete()
                logger.info(f"Сброшены метрики для {manager.full_name} за {today}")
            
            # Также помечаем все транзакции за сегодня как необработанные
            await Transaction.filter(
                manager=manager,
                date__gte=datetime.combine(today, datetime.min.time())
            ).update(processed=False)
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка сброса метрик: {e}")
            return False


# Глобальный экземпляр сервиса
metrics_service = MetricsService()