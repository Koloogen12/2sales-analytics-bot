"""
Обработчики команд Telegram бота
"""
import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from models import Manager
from metrics_service import metrics_service
from google_sheets_service import google_sheets_service
from config import config

logger = logging.getLogger(__name__)

# Создание роутера
router = Router()


class RegistrationStates(StatesGroup):
    """Состояния регистрации"""
    waiting_for_name = State()


# ================ КОМАНДЫ ================

@router.message(CommandStart())
async def cmd_start(message: Message):
    """Команда /start"""
    user_id = message.from_user.id
    
    # Проверяем, зарегистрирован ли пользователь
    manager = await Manager.get_or_none(telegram_user_id=user_id)
    
    if manager:
        await message.answer(
            f"👋 Добро пожаловать, {manager.full_name}!\n\n"
            "Просто описывайте свои действия с клиентами в свободной форме, "
            "и я автоматически буду вести учет ваших метрик.\n\n"
            "📋 Доступные команды:\n"
            "• /stats - моя статистика за сегодня\n"
            "• /help - справка по работе с ботом\n"
            "• /test_export - тестовый экспорт в таблицу (только для админа)"
        )
    else:
        await message.answer(
            "👋 Добро пожаловать в систему учета метрик продаж!\n\n"
            "Для начала работы необходимо зарегистрироваться.\n"
            "Используйте команду /register"
        )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Команда /help"""
    help_text = """
🤖 Как работать с ботом:

1️⃣ После регистрации просто описывайте свои действия с клиентами в свободной форме

2️⃣ Примеры сообщений:
• "Новый клиент Иван купил mpstats за 2000р"
• "Продлил Петров wildberries + marketguru, 3500р"
• "Отказ от Сидорова, не подошла цена"
• "Выдал бонус 500р клиенту Козлову"
• "Получил отзыв от Андреева - очень доволен"
• "Написал 5 новичкам"
• "Разослал сообщения о продлении 10 клиентам"

3️⃣ Бот автоматически:
• Распознает тип действия
• Извлекает данные о клиенте и сумме
• Определяет продукты
• Ведет статистику

4️⃣ Команды:
• /stats - ваша статистика за сегодня
• /register - регистрация (если еще не зарегистрированы)

📊 Каждый день в 23:55 все данные автоматически отправляются в Google Таблицу.
    """
    await message.answer(help_text)


@router.message(Command("register"))
async def cmd_register(message: Message, state: FSMContext):
    """Команда /register"""
    user_id = message.from_user.id
    
    # Проверяем, не зарегистрирован ли уже
    existing_manager = await Manager.get_or_none(telegram_user_id=user_id)
    if existing_manager:
        await message.answer(f"✅ Вы уже зарегистрированы как {existing_manager.full_name}")
        return
    
    await message.answer(
        "📝 Для регистрации введите ваше полное имя (ФИО):\n"
        "Например: Иванов Иван Иванович"
    )
    await state.set_state(RegistrationStates.waiting_for_name)


@router.message(RegistrationStates.waiting_for_name)
async def process_registration_name(message: Message, state: FSMContext):
    """Обработка имени при регистрации"""
    user_id = message.from_user.id
    full_name = message.text.strip()
    username = message.from_user.username
    
    if len(full_name) < 3:
        await message.answer("❌ Имя слишком короткое. Введите полное имя (ФИО):")
        return
    
    try:
        # Создание менеджера
        manager = await Manager.create(
            telegram_user_id=user_id,
            full_name=full_name,
            username=username
        )
        
        await message.answer(
            f"🎉 Регистрация завершена!\n"
            f"👤 Ваше имя: {full_name}\n\n"
            "Теперь вы можете описывать свои действия с клиентами, "
            "и бот будет автоматически вести учет метрик.\n\n"
            "Попробуйте написать что-то вроде:\n"
            "\"Новый клиент Петр купил mpstats за 1500р\""
        )
        
        await state.clear()
        
        logger.info(f"Зарегистрирован новый менеджер: {full_name} (ID: {user_id})")
        
    except Exception as e:
        logger.error(f"Ошибка регистрации: {e}")
        await message.answer("❌ Произошла ошибка при регистрации. Попробуйте еще раз.")


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Команда /stats - статистика за сегодня"""
    user_id = message.from_user.id
    
    manager = await Manager.get_or_none(telegram_user_id=user_id)
    if not manager:
        await message.answer("❌ Вы не зарегистрированы. Используйте /register")
        return
    
    try:
        stats_text = await metrics_service.format_daily_stats(manager)
        await message.answer(stats_text)
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        await message.answer("❌ Ошибка получения статистики")


@router.message(Command("test_export"))
async def cmd_test_export(message: Message):
    """Команда /test_export - тестовый экспорт (только для админа)"""
    user_id = message.from_user.id
    
    if user_id != config.admin_chat_id:
        await message.answer("❌ Команда доступна только администратору")
        return
    
    try:
        await message.answer("📤 Запуск тестового экспорта...")
        
        # Получаем все метрики за сегодня
        all_metrics = await metrics_service.get_all_managers_metrics_today()
        
        if not all_metrics:
            await message.answer("📋 Нет данных для экспорта за сегодня")
            return
        
        # Экспорт в Google Sheets
        success = await google_sheets_service.export_daily_metrics(all_metrics)
        
        if success:
            await message.answer(
                f"✅ Экспорт завершен успешно!\n"
                f"📊 Экспортировано записей: {len(all_metrics)}\n"
                f"👥 Менеджеров: {len(set(m.manager.full_name for m in all_metrics))}"
            )
        else:
            await message.answer("❌ Ошибка экспорта в Google Sheets")
            
    except Exception as e:
        logger.error(f"Ошибка тестового экспорта: {e}")
        await message.answer(f"❌ Ошибка: {e}")


@router.message(Command("reset_stats"))
async def cmd_reset_stats(message: Message):
    """Команда /reset_stats - сброс статистики за сегодня (только для админа)"""
    user_id = message.from_user.id
    
    if user_id != config.admin_chat_id:
        await message.answer("❌ Команда доступна только администратору")
        return
    
    try:
        # Получаем всех менеджеров
        managers = await Manager.all()
        reset_count = 0
        
        for manager in managers:
            success = await metrics_service.reset_manager_metrics(manager)
            if success:
                reset_count += 1
        
        await message.answer(
            f"✅ Сброшена статистика для {reset_count} менеджеров\n"
            f"📊 Все метрики за сегодня обнулены"
        )
        
    except Exception as e:
        logger.error(f"Ошибка сброса статистики: {e}")
        await message.answer(f"❌ Ошибка: {e}")


@router.message(Command("check_connection"))
async def cmd_check_connection(message: Message):
    """Команда /check_connection - проверка соединения с Google Sheets (только для админа)"""
    user_id = message.from_user.id
    
    if user_id != config.admin_chat_id:
        await message.answer("❌ Команда доступна только администратору")
        return
    
    try:
        await message.answer("🔍 Проверка соединения с Google Sheets...")
        
        success = await google_sheets_service.check_connection()
        
        if success:
            last_date = await google_sheets_service.get_last_export_date()
            await message.answer(
                f"✅ Соединение с Google Sheets работает\n"
                f"📅 Последний экспорт: {last_date or 'Нет данных'}"
            )
        else:
            await message.answer("❌ Ошибка соединения с Google Sheets")
            
    except Exception as e:
        logger.error(f"Ошибка проверки соединения: {e}")
        await message.answer(f"❌ Ошибка: {e}")


# ================ ОБРАБОТКА СООБЩЕНИЙ ================

@router.message(F.text & ~F.text.startswith("/"))
async def process_manager_message(message: Message):
    """Обработка обычных сообщений от менеджеров"""
    user_id = message.from_user.id
    
    # Проверяем регистрацию
    manager = await Manager.get_or_none(telegram_user_id=user_id)
    if not manager:
        await message.answer(
            "❌ Вы не зарегистрированы в системе.\n"
            "Используйте команду /register для регистрации."
        )
        return
    
    # Проверяем активность менеджера
    if not manager.is_active:
        await message.answer("❌ Ваш аккаунт деактивирован. Обратитесь к администратору.")
        return
    
    try:
        # Обработка сообщения
        result = await metrics_service.process_manager_message(manager, message.text)
        
        if result["success"]:
            # Отправляем подтверждение
            await message.answer(result["confirmation"])
            
            # Логирование для отладки
            if config.debug:
                parsed_data = result.get("parsed_data", {})
                confidence = parsed_data.get("confidence", 0)
                if confidence < 0.7:
                    await message.answer(
                        f"⚠️ Низкая уверенность в распознавании: {confidence:.0%}\n"
                        f"Если данные неверны, опишите действие более подробно."
                    )
        else:
            # Ошибка обработки
            await message.answer(result["confirmation"])
            
            # Предложение помощи
            await message.answer(
                "💡 Попробуйте описать действие более подробно.\n"
                "Например: \"Новый клиент Иван купил mpstats за 2000р\"\n"
                "Или используйте /help для примеров."
            )
            
    except Exception as e:
        logger.error(f"Критическая ошибка обработки сообщения: {e}")
        await message.answer(
            "❌ Произошла критическая ошибка.\n"
            "Попробуйте еще раз или обратитесь к администратору."
        )


# ================ ОБРАБОТКА СПЕЦИАЛЬНЫХ СООБЩЕНИЙ ================

@router.message(F.photo)
async def process_photo(message: Message):
    """Обработка фотографий"""
    await message.answer(
        "📷 Получена фотография, но пока что бот обрабатывает только текстовые сообщения.\n"
        "Опишите текстом, что изображено на фото."
    )


@router.message(F.document)
async def process_document(message: Message):
    """Обработка документов"""
    await message.answer(
        "📄 Получен документ, но пока что бот обрабатывает только текстовые сообщения.\n"
        "Опишите текстом содержание документа."
    )


@router.message(F.voice)
async def process_voice(message: Message):
    """Обработка голосовых сообщений"""
    await message.answer(
        "🎤 Получено голосовое сообщение, но пока что бот обрабатывает только текст.\n"
        "Напишите текстом то же самое."
    )


# ================ ОБРАБОТКА НЕИЗВЕСТНЫХ КОМАНД ================

@router.message(F.text.startswith("/"))
async def unknown_command(message: Message):
    """Обработка неизвестных команд"""
    await message.answer(
        "❓ Неизвестная команда.\n\n"
        "📋 Доступные команды:\n"
        "• /start - начало работы\n"
        "• /help - справка\n"
        "• /register - регистрация\n"
        "• /stats - статистика за сегодня\n\n"
        "Или просто опишите ваши действия с клиентами в свободной форме."
    )


# ================ MIDDLEWARE ДЛЯ ЛОГИРОВАНИЯ ================

@router.message.middleware()
async def logging_middleware(handler, event: Message, data: dict):
    """Middleware для логирования сообщений"""
    user_id = event.from_user.id
    username = event.from_user.username
    text = event.text or f"[{event.content_type}]"
    
    logger.info(f"Сообщение от {user_id} (@{username}): {text[:100]}")
    
    # Продолжаем обработку
    return await handler(event, data)