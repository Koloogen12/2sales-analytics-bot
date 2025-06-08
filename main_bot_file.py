"""
Главный файл Telegram бота для учета метрик продаж
"""
import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from tortoise import Tortoise

# Импорты модулей проекта
from config import config
from handlers import router
from scheduler import scheduler_service
from notification_service import notification_service

# Настройка логирования
logging.basicConfig(
    level=logging.INFO if not config.debug else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)

# Отключаем избыточные логи
logging.getLogger('aiogram').setLevel(logging.WARNING)
logging.getLogger('tortoise').setLevel(logging.WARNING)
logging.getLogger('apscheduler').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


async def init_database():
    """Инициализация базы данных"""
    try:
        await Tortoise.init(
            db_url=config.database_url,
            modules={'models': ['models']}
        )
        
        # Создание схем базы данных
        await Tortoise.generate_schemas()
        
        logger.info("✅ База данных инициализирована")
        
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации базы данных: {e}")
        raise


async def shutdown_database():
    """Закрытие соединений с базой данных"""
    try:
        await Tortoise.close_connections()
        logger.info("✅ Соединения с базой данных закрыты")
    except Exception as e:
        logger.error(f"❌ Ошибка закрытия базы данных: {e}")


async def startup_notification():
    """Уведомление о запуске бота"""
    try:
        startup_message = (
            f"🚀 Бот запущен успешно!\n\n"
            f"⏰ Время: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"📊 Режим отладки: {'Включен' if config.debug else 'Отключен'}\n"
            f"📅 Время ежедневного экспорта: {config.daily_export_time}\n"
            f"🔗 Google Sheet ID: {config.google_sheet_id}\n"
            f"🤖 Модель GPT: {config.openai_model}"
        )
        
        await notification_service.notify_admin(startup_message)
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки уведомления о запуске: {e}")


async def main():
    """Главная функция бота"""
    logger.info("🚀 Запуск бота...")
    
    try:
        # Инициализация базы данных
        await init_database()
        
        # Создание бота и диспетчера
        bot = Bot(
            token=config.telegram_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        
        dp = Dispatcher()
        
        # Регистрация роутеров
        dp.include_router(router)
        
        # Запуск планировщика
        scheduler_service.start()
        
        # Уведомление о запуске
        await startup_notification()
        
        logger.info("✅ Бот готов к работе")
        logger.info(f"📊 Следующий экспорт: {scheduler_service.get_next_export_time()}")
        
        # Запуск polling
        await dp.start_polling(
            bot,
            allowed_updates=["message", "callback_query"],
            skip_updates=True  # Пропускаем старые сообщения
        )
        
    except KeyboardInterrupt:
        logger.info("🛑 Получен сигнал остановки")
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        
        # Уведомление администратора об ошибке
        try:
            await notification_service.send_error_notification(
                "Критическая ошибка бота",
                str(e)
            )
        except:
            pass
        
        raise
        
    finally:
        # Остановка планировщика
        try:
            scheduler_service.stop()
        except:
            pass
        
        # Закрытие уведомлений
        try:
            await notification_service.close()
        except:
            pass
        
        # Закрытие базы данных
        await shutdown_database()
        
        logger.info("🏁 Бот остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Фатальная ошибка: {e}")
        sys.exit(1)