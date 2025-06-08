"""
Планировщик для автоматического экспорта метрик
"""
import logging
import asyncio
from datetime import datetime, time
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import config
from metrics_service import metrics_service
from google_sheets_service import google_sheets_service
from models import Manager
from notification_service import notification_service

logger = logging.getLogger(__name__)


class SchedulerService:
    """Сервис планировщика задач"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._setup_jobs()
    
    def _setup_jobs(self):
        """Настройка заданий планировщика"""
        try:
            # Парсинг времени экспорта
            hour, minute = map(int, config.daily_export_time.split(":"))
            
            # Ежедневный экспорт метрик
            self.scheduler.add_job(
                func=self.daily_export_job,
                trigger=CronTrigger(hour=hour, minute=minute),
                id="daily_export",
                name="Ежедневный экспорт метрик",
                replace_existing=True
            )
            
            # Уведомление менеджеров о завершении дня (за 30 минут до экспорта)
            notification_hour = hour
            notification_minute = minute - 30
            if notification_minute < 0:
                notification_minute += 60
                notification_hour -= 1
                if notification_hour < 0:
                    notification_hour = 23
            
            self.scheduler.add_job(
                func=self.daily_reminder_job,
                trigger=CronTrigger(hour=notification_hour, minute=notification_minute),
                id="daily_reminder",
                name="Напоминание о завершении дня",
                replace_existing=True
            )
            
            # Еженедельная статистика (каждое воскресенье в 20:00)
            self.scheduler.add_job(
                func=self.weekly_stats_job,
                trigger=CronTrigger(day_of_week=6, hour=20, minute=0),  # Воскресенье
                id="weekly_stats",
                name="Еженедельная статистика",
                replace_existing=True
            )
            
            logger.info(f"✅ Планировщик настроен:")
            logger.info(f"📊 Ежедневный экспорт: {config.daily_export_time}")
            logger.info(f"🔔 Напоминания: {notification_hour:02d}:{notification_minute:02d}")
            logger.info(f"📈 Еженедельная статистика: Воскресенье 20:00")
            
        except Exception as e:
            logger.error(f"❌ Ошибка настройки планировщика: {e}")
            raise
    
    async def daily_export_job(self):
        """Ежедневное задание экспорта метрик"""
        try:
            logger.info("🕒 Запуск ежедневного экспорта метрик")
            
            # Получение всех метрик за сегодня
            all_metrics = await metrics_service.get_all_managers_metrics_today()
            
            if not all_metrics:
                logger.info("📋 Нет метрик для экспорта за сегодня")
                await notification_service.notify_admin(
                    "📋 Ежедневный экспорт: нет данных за сегодня"
                )
                return
            
            # Экспорт в Google Sheets
            success = await google_sheets_service.export_daily_metrics(all_metrics)
            
            if success:
                # Подготовка статистики для уведомления
                total_managers = len(set(m.manager.full_name for m in all_metrics))
                total_revenue = sum(m.total_revenue for m in all_metrics)
                total_clients = sum(m.new_clients + m.active_clients for m in all_metrics)
                
                success_message = (
                    f"✅ Ежедневный экспорт завершен успешно!\n\n"
                    f"📊 Статистика за {datetime.now().strftime('%Y-%m-%d')}:\n"
                    f"👥 Активных менеджеров: {total_managers}\n"
                    f"💰 Общая выручка: {total_revenue:,.0f}₽\n"
                    f"🤝 Всего клиентов: {total_clients}\n"
                    f"📄 Экспортировано записей: {len(all_metrics)}"
                )
                
                # Уведомление администратора
                await notification_service.notify_admin(success_message)
                
                # Уведомление менеджеров об успешном экспорте
                for metrics in all_metrics:
                    if metrics.manager.is_active:
                        await notification_service.notify_manager(
                            metrics.manager,
                            f"✅ Ваши данные за сегодня успешно сохранены в систему!\n"
                            f"💰 Ваша выручка: {metrics.total_revenue:,.0f}₽\n"
                            f"🤝 Клиентов: {metrics.new_clients + metrics.active_clients}"
                        )
                
                logger.info(f"✅ Экспорт завершен: {len(all_metrics)} записей")
                
            else:
                error_message = "❌ Ошибка ежедневного экспорта в Google Sheets"
                await notification_service.notify_admin(error_message)
                logger.error(error_message)
                
        except Exception as e:
            error_message = f"❌ Критическая ошибка ежедневного экспорта: {e}"
            logger.error(error_message)
            await notification_service.notify_admin(error_message)
    
    async def daily_reminder_job(self):
        """Ежедневное напоминание менеджерам"""
        try:
            logger.info("🔔 Отправка ежедневных напоминаний")
            
            # Получение всех активных менеджеров
            managers = await Manager.filter(is_active=True)
            
            for manager in managers:
                try:
                    # Получение статистики за сегодня
                    stats_text = await metrics_service.format_daily_stats(manager)
                    
                    reminder_text = (
                        f"🔔 Скоро завершение рабочего дня!\n\n"
                        f"Через 30 минут (в {config.daily_export_time}) "
                        f"ваши данные будут автоматически сохранены.\n\n"
                        f"{stats_text}\n\n"
                        f"💡 Если есть еще неучтенные действия, опишите их сейчас!"
                    )
                    
                    await notification_service.notify_manager(manager, reminder_text)
                    
                except Exception as e:
                    logger.error(f"Ошибка отправки напоминания {manager.full_name}: {e}")
            
            logger.info(f"✅ Отправлено напоминаний: {len(managers)}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки напоминаний: {e}")
    
    async def weekly_stats_job(self):
        """Еженедельная статистика"""
        try:
            logger.info("📈 Генерация еженедельной статистики")
            
            # Здесь можно добавить логику сбора недельной статистики
            # Пока что просто уведомляем администратора
            
            await notification_service.notify_admin(
                "📈 Еженедельная статистика\n\n"
                "📊 Для детальной аналитики перейдите в Google Таблицу.\n"
                f"🔗 Ссылка: https://docs.google.com/spreadsheets/d/{config.google_sheet_id}"
            )
            
            logger.info("✅ Еженедельная статистика отправлена")
            
        except Exception as e:
            logger.error(f"❌ Ошибка еженедельной статистики: {e}")
    
    def start(self):
        """Запуск планировщика"""
        try:
            self.scheduler.start()
            logger.info("✅ Планировщик запущен")
            
            # Показываем следующие запланированные задания
            jobs = self.scheduler.get_jobs()
            for job in jobs:
                next_run = job.next_run_time
                if next_run:
                    logger.info(f"📅 {job.name}: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
                    
        except Exception as e:
            logger.error(f"❌ Ошибка запуска планировщика: {e}")
            raise
    
    def stop(self):
        """Остановка планировщика"""
        try:
            self.scheduler.shutdown()
            logger.info("✅ Планировщик остановлен")
        except Exception as e:
            logger.error(f"❌ Ошибка остановки планировщика: {e}")
    
    async def manual_export(self) -> bool:
        """Ручной запуск экспорта"""
        try:
            logger.info("🚀 Ручной запуск экспорта")
            await self.daily_export_job()
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка ручного экспорта: {e}")
            return False
    
    def get_next_export_time(self) -> str:
        """Получение времени следующего экспорта"""
        try:
            export_job = self.scheduler.get_job("daily_export")
            if export_job and export_job.next_run_time:
                return export_job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")
            return "Не запланировано"
        except Exception as e:
            logger.error(f"Ошибка получения времени экспорта: {e}")
            return "Ошибка"


# Глобальный экземпляр планировщика
scheduler_service = SchedulerService()
