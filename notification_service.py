"""
Сервис уведомлений через Telegram
"""
import logging
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from config import config
from models import Manager

logger = logging.getLogger(__name__)


class NotificationService:
    """Сервис для отправки уведомлений"""
    
    def __init__(self):
        self.bot = Bot(token=config.telegram_token)
    
    async def notify_manager(self, manager: Manager, message: str) -> bool:
        """
        Отправка уведомления менеджеру
        
        Args:
            manager: Менеджер для уведомления
            message: Текст сообщения
            
        Returns:
            True если успешно отправлено
        """
        try:
            await self.bot.send_message(
                chat_id=manager.telegram_user_id,
                text=message,
                parse_mode=None  # Отключаем парсинг для безопасности
            )
            
            logger.info(f"✅ Уведомление отправлено {manager.full_name}")
            return True
            
        except TelegramForbiddenError:
            # Пользователь заблокировал бота
            logger.warning(f"⚠️ Пользователь {manager.full_name} заблокировал бота")
            
            # Деактивируем менеджера
            manager.is_active = False
            await manager.save()
            
            return False
            
        except TelegramBadRequest as e:
            logger.error(f"❌ Ошибка Telegram API для {manager.full_name}: {e}")
            return False
            
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка отправки уведомления {manager.full_name}: {e}")
            return False
    
    async def notify_admin(self, message: str) -> bool:
        """
        Отправка уведомления администратору
        
        Args:
            message: Текст сообщения
            
        Returns:
            True если успешно отправлено
        """
        try:
            await self.bot.send_message(
                chat_id=config.admin_chat_id,
                text=f"🔔 Системное уведомление\n\n{message}",
                parse_mode=None
            )
            
            logger.info("✅ Уведомление администратору отправлено")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления администратору: {e}")
            return False
    
    async def broadcast_to_all_managers(self, message: str) -> dict:
        """
        Рассылка сообщения всем активным менеджерам
        
        Args:
            message: Текст сообщения
            
        Returns:
            Статистика рассылки
        """
        managers = await Manager.filter(is_active=True)
        
        success_count = 0
        failed_count = 0
        blocked_count = 0
        
        for manager in managers:
            try:
                await self.bot.send_message(
                    chat_id=manager.telegram_user_id,
                    text=message,
                    parse_mode=None
                )
                success_count += 1
                
            except TelegramForbiddenError:
                # Пользователь заблокировал бота
                blocked_count += 1
                manager.is_active = False
                await manager.save()
                
            except Exception as e:
                failed_count += 1
                logger.error(f"Ошибка рассылки для {manager.full_name}: {e}")
        
        stats = {
            "total": len(managers),
            "success": success_count,
            "failed": failed_count,
            "blocked": blocked_count
        }
        
        logger.info(f"📤 Рассылка завершена: {stats}")
        
        # Уведомляем администратора о результатах
        await self.notify_admin(
            f"📤 Результаты рассылки:\n"
            f"• Всего менеджеров: {stats['total']}\n"
            f"• Успешно: {stats['success']}\n"
            f"• Ошибки: {stats['failed']}\n"
            f"• Заблокировали бота: {stats['blocked']}"
        )
        
        return stats
    
    async def send_system_status(self) -> bool:
        """
        Отправка статуса системы администратору
        
        Returns:
            True если успешно отправлено
        """
        try:
            # Получение статистики
            total_managers = await Manager.filter(is_active=True).count()
            total_all_managers = await Manager.all().count()
            
            status_message = (
                f"📊 Статус системы:\n\n"
                f"👥 Активных менеджеров: {total_managers}\n"
                f"👥 Всего зарегистрированных: {total_all_managers}\n"
                f"🤖 Бот: Работает\n"
                f"📊 Google Sheets: {'✅' if await self._check_sheets_connection() else '❌'}\n"
                f"⏰ Планировщик: Активен"
            )
            
            return await self.notify_admin(status_message)
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки статуса системы: {e}")
            return False
    
    async def _check_sheets_connection(self) -> bool:
        """Проверка соединения с Google Sheets"""
        try:
            from google_sheets_service import google_sheets_service
            return await google_sheets_service.check_connection()
        except Exception:
            return False
    
    async def send_error_notification(self, error_type: str, error_message: str, manager: Manager = None) -> bool:
        """
        Отправка уведомления об ошибке
        
        Args:
            error_type: Тип ошибки
            error_message: Текст ошибки
            manager: Менеджер (если ошибка связана с конкретным пользователем)
            
        Returns:
            True если успешно отправлено
        """
        try:
            notification_text = f"❌ Ошибка в системе\n\n"
            notification_text += f"🔍 Тип: {error_type}\n"
            notification_text += f"📝 Описание: {error_message}\n"
            
            if manager:
                notification_text += f"👤 Менеджер: {manager.full_name} (ID: {manager.telegram_user_id})\n"
            
            notification_text += f"⏰ Время: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            return await self.notify_admin(notification_text)
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления об ошибке: {e}")
            return False
    
    async def close(self):
        """Закрытие соединения с ботом"""
        try:
            await self.bot.session.close()
            logger.info("✅ Соединение с Telegram API закрыто")
        except Exception as e:
            logger.error(f"❌ Ошибка закрытия соединения: {e}")


# Глобальный экземпляр сервиса уведомлений
notification_service = NotificationService()
